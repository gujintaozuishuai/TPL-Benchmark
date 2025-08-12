import os
import re
import csv
import toml
from tqdm import tqdm
from collections import defaultdict, deque


def find_project_root(directory):
    for root, dirs, files in os.walk(directory):
        if ('build.gradle.kts' in files and 'settings.gradle.kts' in files) or ('build.gradle.kts' in files and 'settings.gradle' in files):
            return root
    return None


def load_gradle_properties(file_path):
    properties = {}
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                match = re.findall(r'(\w[\w.]*)\s*=\s*(.*)', line)
                for key, value in match:
                    properties[key] = value
    return properties


def parse_gradle_ext_block(block_content):
    ext = {}
    block_content = remove_comments(block_content)

    # Handle simple assignments
    simple_matches = re.findall(r'["\']?(\w+)["\']?\s*[=:]\s*["\']([^"\']+)["\']', block_content)
    for key, value in simple_matches:
        ext[key] = value

    # Handle assignments with functions or integers
    simple_function_matches = re.findall(r'["\']?(\w+)["\']?\s*[=:]\s*([\w()]+)', block_content)
    for key, value in simple_function_matches:
        ext[key] = value

    # Handle nested dictionary assignments and extract key-value pairs
    nested_matches = re.findall(r'["\']?(\w+)["\']?\s*=\s*\[(.*)\]', block_content, re.DOTALL)
    for key, value in nested_matches:
        ext.update(parse_gradle_ext_block(value))

    return ext


def load_gradle_ext(file_path):
    ext = {}
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            content = remove_comments(content)

            # Handle single line ext assignments
            single_line_matches = re.findall(r'ext\.(\w+)\s*=\s*["\']([^"\']+)["\']', content)
            for key, value in single_line_matches:
                ext[key] = value

            # Handle dictionary-style ext assignments
            dict_style_matches = re.findall(r'ext\.(\w+)\s*=\s*\[(.*?)\]', content, re.DOTALL)
            for key, value in dict_style_matches:
                nested_pairs = re.findall(r'["\']?(\w+)["\']?\s*:\s*["\']?([^"\',]+)["\']?', value)
                for nested_key, nested_value in nested_pairs:
                    ext[nested_key] = nested_value

            # Handle block-style ext assignments
            block_matches = re.findall(r'(?:ext|project\.ext)\s*{\s*(.*?)\s*}', content, re.DOTALL)
            for block in block_matches:
                ext.update(parse_gradle_ext_block(block))

            # Handle inline ext assignments
            inline_matches = re.findall(r'ext\.(\w+)\s*=\s*["\']([^"\']+)["\']', content)
            for key, value in inline_matches:
                ext[key] = value

            # Handle standalone dictionary assignments
            standalone_dict_matches = re.findall(r'(\w+)\s*=\s*\[\s*(.*?)\s*\]', content, re.DOTALL)
            for key, value in standalone_dict_matches:
                nested_pairs = re.findall(r'["\']?(\w+)["\']?\s*:\s*["\']?([^"\',]+)["\']?', value)
                for nested_key, nested_value in nested_pairs:
                    ext[nested_key] = nested_value

            val_matches = re.findall(r'val\s+(\w+)\s+by\s+extra\s*[\(\{]\s*"([^"]+)"\s*[\)\}]', content)
            for key, value in val_matches:
                ext[key] = value
    return ext


'''
def parse_gradle_ext_block(block_content):
    ext = {}
    block_content = remove_comments(block_content)

    # Handle simple assignments
    simple_matches = re.findall(r'(\w+)\s*=\s*["\']([^"\']+)["\']', block_content)
    for key, value in simple_matches:
        ext[key] = value

    # Handle dictionary assignments
    nested_matches = re.findall(r'(\w+)\s*=\s*\[(.*?)\]', block_content, re.DOTALL)
    for key, value in nested_matches:
        nested_dict = {}
        nested_pairs = re.findall(r'(\w+)\s*:\s*["\']([^"\']+)["\']', value)
        for nested_key, nested_value in nested_pairs:
            nested_dict[nested_key] = nested_value
        ext[key] = nested_dict

    return ext



def load_gradle_ext(file_path):
    ext = {}
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            # Match single-line ext assignments
            single_line_matches = re.findall(r'ext\.(\w+)\s*=\s*["\']([^"\']+)["\']', content)
            for key, value in single_line_matches:
                ext[key] = value

            # Match and parse ext blocks
            block_matches = re.findall(r'(?:ext|project\.ext)\s*{\s*(.*?)\s*}', content, re.DOTALL)
            for block in block_matches:
                ext.update(parse_gradle_ext_block(block))

    return ext

'''


# 一定要考虑到兼容之前的特殊情况，而不是直接处理当前的特殊情况，这是难点，也是麻烦的地方


def extract_local_properties(content):
    local_properties = {}
    matches = re.findall(r'(\w+)\s*=\s*["\']?([\w\.\-]+)["\']?', content)
    for match in matches:
        local_properties[match[0]] = match[1]
    return local_properties


def extract_local_ext(content):
    local_ext = {}
    matches = re.findall(r'(?:ext|project\.ext)\s*{\s*(.*?)\s*}', content, re.DOTALL)
    for match in matches:
        local_ext.update(parse_gradle_ext_block(match))
    return local_ext


def resolve_version(version, properties, project_properties, root_properties):
    patterns = [
        r'\$\{?([\w\.]+)\}?'  # Match everything within ${} or starting with $
    ]

    for pattern in patterns:
        matches = re.finditer(pattern, version)
        for match in matches:
            # var_name = match.group(1)
            full_var_name = match.group(1)  # Get the full matched string

            # Split the variable name by dot and get the last part
            var_name = full_var_name.split('.')[-1]

            # Search in all properties
            if var_name in properties:
                resolved_value = properties[var_name]
            elif var_name in project_properties:
                resolved_value = project_properties[var_name]
            elif var_name in root_properties:
                resolved_value = root_properties[var_name]
            else:
                continue

            if isinstance(resolved_value, dict):
                raise ValueError(f"Cannot resolve variable {var_name} as it maps to a dictionary")
            version = version.replace(match.group(0), resolved_value)

    return version


def remove_comments(content):
    # Remove /* */ block comments
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    # Remove // line comments
    content = re.sub(r'//.*', '', content)
    return content


def extract_dependencies(file_path, root_properties, root_ext, root_toml):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    # Remove comments from the content
    content = remove_comments(content)

    local_properties = extract_local_properties(content)  #
    local_ext = extract_local_ext(content)  #
    all_properties = {**root_properties, **root_ext, **local_properties, **local_ext}

    # Regex to match dependencies with various keywords, excluding unwanted ones
    # 第一个正则表达式用于匹配标准依赖项格式
    dependency_pattern = re.compile(
        r'[\t ]*(withAnalyticsImplementation|"PlayStoreImplementation"|androidImplementation|nightlyImplementation|gplayImplementation|natives|compile|appengineSdk|releaseCompile|api|implementation|playImplementation|playstoreImplementation|largeImplementation|amazonImplementation|githubImplementation|releaseImplementation|pureImplementation|coreLibraryDesugaring)\b[ \(\'"]+([\w\.\-]+):([\w\.\-]+)(?::([\w\.\-\$\{\}@\[\], ]+))?[\'"\)]*[\s\{]*'
    )
    # |releaseCompile
    dependencies = dependency_pattern.findall(content)

    # 第二个正则表达式用于匹配group, name, version格式的依赖项
    group_name_version_pattern = re.compile(
        r'[\t ]*(compile|implementation|api)\s+group:\s*[\'"]([\w\.\-]+)[\'"],\s*name:\s*[\'"]([\w\.\-]+)[\'"],\s*version:\s*[\'"]([\w\.\-\[\],]+)[\'"]'
    )

    group_name_version_matches = group_name_version_pattern.findall(content)

    toml_variable_pattern = re.compile(
        r'(?:"marketImplementation"|"fullImplementation"|"minimalImplementation"|firebaseImplementation|runtimeOnly|withAnalyticsImplementation|"PlayStoreImplementation"|androidImplementation|nightlyImplementation|gplayImplementation|natives|compile|appengineSdk|releaseCompile|api|implementation|playImplementation|playstoreImplementation|largeImplementation|amazonImplementation|githubImplementation|releaseImplementation|pureImplementation|coreLibraryDesugaring)\s*\(?platform\(?\s*([\w\.]+)\s*\)*|'
        r'(?:"marketImplementation"|"fullImplementation"|"minimalImplementation"|firebaseImplementation|runtimeOnly|withAnalyticsImplementation|"PlayStoreImplementation"|androidImplementation|nightlyImplementation|gplayImplementation|natives|compile|appengineSdk|releaseCompile|api|implementation|playImplementation|playstoreImplementation|largeImplementation|amazonImplementation|githubImplementation|releaseImplementation|pureImplementation|coreLibraryDesugaring)\s*\(?\s*([\w\.]+)\s*\)?'
    )
    toml_variable_matches = toml_variable_pattern.findall(content)

    # Regex to match submodule dependencies
    submodule_pattern = re.compile(
        # r'(compile|implementation|wearApp)\s+project\(["\'](:[\w\-]+)["\']\)|'        #wearApp  F:\all_readme_src_apk\Healthy Heart Rate_3_Apkpure\bachamada-master
        # r'(compile|implementation|wearApp)\s+project\(path:\s*["\'](:[\w\-]+)["\']'   #wearApp  F:\all_readme_src_apk\Excuser_1.2_APKPure\Excuser-master
        r'(annotationProcessor|compile|implementation|api|"PlayStoreImplementation")[\s\(]+project\s*\(\s*["\'](?::[\w\-.]+)*:([\w\-.]+)["\']\s*\)+|'
        r'(annotationProcessor|compile|implementation|api|"PlayStoreImplementation")[\s\(]+project\s*\(\s*path:\s*["\'](?::[\w\-.]+)*:([\w\-.]+)["\']\s*\)+'
    )
    # submodule_pattern = re.compile(r'(compile|implementation)\s+project\(["\'](:[\w\-]+)["\']\)')
    submodules = submodule_pattern.findall(content)

    # 提取形如implementation(projects.core.ui)的子模块
    submodule_pattern2 = re.compile(
        r'(annotationProcessor|compile|implementation|api|"PlayStoreImplementation")\s*\(\s*projects\.([\w\.]+)\s*\)'
    )
    submodules2 = submodule_pattern2.findall(content)

    # 匹配platform
    platform_pattern = re.compile(
        r'[\t ]*(withAnalyticsImplementation|androidImplementation|nightlyImplementation|gplayImplementation|natives|compile|appengineSdk|releaseCompile|api|implementation|playImplementation|playstoreImplementation|largeImplementation|amazonImplementation|githubImplementation|releaseImplementation|pureImplementation|coreLibraryDesugaring)\b[ \(\'"]+platform\(["\']([\w\.\-]+):([\w\.\-]+):([\w\.\-\$\{\}@\[\], ]+)[\'"\)]*[\s\{]*'
    )
    # |releaseCompile
    platforms = platform_pattern.findall(content)

    resolved_dependencies = []
    for dep in dependencies:
        keyword, group, artifact, version = dep
        # version = resolve_version(version, all_properties)
        version = resolve_version(version, all_properties, local_properties, root_properties)
        resolved_dependencies.append((group, artifact, version))

    for dep in group_name_version_matches:
        keyword, group, artifact, version = dep
        # version = resolve_version(version, all_properties)
        version = resolve_version(version, all_properties, local_properties, root_properties)
        resolved_dependencies.append((group, artifact, version))

    for dep in platforms:
        keyword, group, artifact, version = dep
        # version = resolve_version(version, all_properties)
        version = resolve_version(version, all_properties, local_properties, root_properties)
        resolved_dependencies.append((group, artifact, version))

    for toml in toml_variable_matches:
        for toml_var in toml:
            if toml_var in root_toml.keys():
                # 将 toml 变量解析为对应的库依赖项
                if isinstance(root_toml[toml_var], list):
                    for val in root_toml[toml_var]:
                        res = val.split(":")
                        resolved_dependencies.append((res[0], res[1], res[2]))
                else:
                    res = root_toml[toml_var].split(":")
                    resolved_dependencies.append((res[0], res[1], res[2]))

    # submodule_dependencies = [sub[1].strip(':') for sub in submodules]
    submodule_dependencies = [sub[1].strip(':') if sub[1] else sub[3].strip(':') for sub in submodules]
    submodule_dependencies.extend([sub[1].split('.')[-1] for sub in submodules2])

    return resolved_dependencies, submodule_dependencies, content, ("android.application" in content or "androidApplication" in content or "libs.plugins.android" in content)     #libs.plugins.androidApplication

#com.android.application  libs.plugins.android.application  libs.plugins.androidApplication  libs.plugins.android

'''
def scan_project_directory(directory_path):
    all_dependencies = {}
    root_properties = load_gradle_properties(os.path.join(directory_path, 'gradle.properties'))
    root_ext = load_gradle_ext(os.path.join(directory_path, 'build.gradle'))

    module_dependencies = {}

    # First pass: collect dependencies for all modules
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            if file == 'build.gradle':
                file_path = os.path.join(root, file)
                #module_name = os.path.relpath(root, directory_path).replace(os.sep, ':')
                module_name = os.path.basename(root)
                dependencies, submodules, content = extract_dependencies(file_path, root_properties, root_ext)
                if dependencies or submodules:    #如果子模块中依赖为空，则不记录这个子模块
                    module_dependencies[module_name] = {
                        'dependencies': dependencies,
                        'submodules': submodules,
                        'content': content
                    }

    # Second pass: resolve submodule dependencies
    for module_name, module_data in module_dependencies.items():
        content = module_data['content']
        dependencies = module_data['dependencies']
        submodules = module_data['submodules']

        for submodule_name in submodules:
            submodule_data = module_dependencies.get(submodule_name)
            if submodule_data:
                dependencies.extend(submodule_data['dependencies'])

        all_dependencies[module_name] = dependencies

    return all_dependencies
'''


def topological_sort(modules):
    # Create a graph and in-degree count for each module
    graph = defaultdict(list)
    in_degree = {module: 0 for module in modules}

    for module, data in modules.items():
        for submodule in data['submodules']:
            graph[submodule].append(module)
            in_degree[module] += 1

    # Perform topological sorting using Kahn's algorithm
    queue = deque([module for module in in_degree if in_degree[module] == 0])
    sorted_modules = []

    while queue:
        module = queue.popleft()
        sorted_modules.append(module)
        for neighbor in graph[module]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)


    # Include modules that have dependencies but no submodules
    remaining_modules = [module for module in modules if module not in sorted_modules]
    sorted_modules.extend(remaining_modules)

    return sorted_modules


def parse_libraries(libraries, versions, bundles):
    parsed_libraries = {}

    for lib, value in libraries.items():
        group = name = version = None

        if isinstance(value, str):
            group, name, version = value.split(':')
        elif 'module' in value:
            group, name = value['module'].split(':')
            version_info = value.get('version')
            if isinstance(version_info, dict):
                if 'ref' in version_info:
                    version = versions.get(version_info['ref'])
                elif 'require' in version_info:
                    version = version_info['require']
                elif 'prefer' in version_info:
                    version = version_info['prefer']
                elif 'strictly' in version_info:
                    version = version_info['strictly']
            else:
                version = version_info
        elif 'group' in value and 'name' in value and 'version' in value:
            group = value['group']
            name = value['name']
            version_info = value['version']
            if isinstance(version_info, dict):
                if 'ref' in version_info:
                    version = versions.get(version_info['ref'])
                elif 'require' in version_info:
                    version = version_info['require']
                elif 'prefer' in version_info:
                    version = version_info['prefer']
                elif 'strictly' in version_info:
                    version = version_info['strictly']
            else:
                version = version_info
        elif 'group' in value and 'name' in value:
            group = value['group']
            name = value['name']
            version = ''

        if group and name:
            parsed_libraries[lib] = f"{group}:{name}:{version}"

    # 解析 bundles 部分
    for bundle, libs in bundles.items():
        bundle = bundle.replace('-', '.')
        bundle_key = f"bundles.{bundle}"
        bundle_libraries = [parsed_libraries[lib] for lib in libs if lib in parsed_libraries]
        parsed_libraries[bundle_key] = bundle_libraries

    return parsed_libraries


def load_toml(base_dir):
    all_libraries = {}

    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith('.versions.toml') or file.endswith('libs.toml'):
                file_path = os.path.join(root, file)
                # file_prefix = os.path.splitext(file)[0].replace('.', '_')
                file_prefix = file.split('.')[0]

                with open(file_path, 'r') as toml_file:
                    toml_content = toml.load(toml_file)

                versions_section = toml_content.get('versions', {})
                libraries_section = toml_content.get('libraries', {})
                bundles_section = toml_content.get('bundles', {})
                parsed_libraries = parse_libraries(libraries_section, versions_section, bundles_section)

                for lib, mapping in parsed_libraries.items():
                    lib = lib.replace('-', '.')
                    lib = lib.replace('_', '.')
                    all_libraries[f"{file_prefix}.{lib}"] = mapping
                    # if isinstance(mapping, list):
                    #     all_libraries[f"{file_prefix}.{lib}"] = ", ".join(mapping)
                    # else:
                    #     all_libraries[f"{file_prefix}.{lib}"] = mapping

    return all_libraries


def scan_project_directory(directory_path):
    all_dependencies = {}
    root_properties = load_gradle_properties(os.path.join(directory_path, 'gradle.properties'))
    root_ext = load_gradle_ext(os.path.join(directory_path, 'build.gradle.kts'))
    root_toml = load_toml(directory_path)

    module_dependencies = {}
    main_module_flag = ''

    # First pass: collect dependencies for all modules
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            if file == 'build.gradle.kts':
                file_path = os.path.join(root, file)
                module_name = os.path.basename(root)
                dependencies, submodules, content, flag = extract_dependencies(file_path, root_properties, root_ext, root_toml)
                if dependencies or submodules:
                    module_dependencies[module_name] = {
                        'dependencies': dependencies,
                        'submodules': submodules,
                        'content': content
                    }
                else:
                    module_dependencies[module_name] = {
                        'dependencies': [],
                        'submodules': [],
                        'content': content
                    }
                if flag:
                    main_module_flag = module_name

    # Second pass: resolve submodule dependencies using topological sort
    sorted_modules = topological_sort(module_dependencies)
    #main_module_flag = sorted_modules[-1]

    for module_name in sorted_modules:
        module_data = module_dependencies[module_name]
        dependencies = module_data['dependencies']
        submodules = module_data['submodules']

        # Resolve submodule dependencies
        for submodule_name in submodules:
            submodule_data = module_dependencies.get(submodule_name)
            if submodule_data:
                dependencies.extend(submodule_data['dependencies'])

        all_dependencies[module_name] = dependencies

    return all_dependencies, main_module_flag


# 加载和筛选CSV文件
def load_and_filter_csv(file_path):
    filtered_folders = []
    with open(file_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if int(row['build.gradle Count']) > 3 and int(row['build.gradle.kts Count']) == 0:
                filtered_folders.append(row['App Folder'])
    return filtered_folders


def has_txt_file_in_current_directory(initial_directory):
    for filename in os.listdir(initial_directory):
        if filename.endswith('.txt'):
            return True
    return False

'''
def main():
    csv_file_path = r'analysis_readme_build_files_details.csv'
    base_directory = r'H:\all_readme_src_apk'
    filtered_folders = load_and_filter_csv(csv_file_path)


    for folder in filtered_folders:
        app_folder_path = os.path.join(base_directory, folder)
        print(f'folder: {folder}')
        # 找到源码文件夹（假设它是除了apk文件之外的唯一文件夹）
        for item in os.listdir(app_folder_path):
            initial_directory = os.path.join(app_folder_path, item)
            if os.path.isdir(initial_directory):
                # 遍历源码文件夹以提取依赖项
                project_directory = find_project_root(initial_directory)
                if project_directory:
                    dependencies = scan_project_directory(project_directory)
                    if dependencies:
                        for app, deps in dependencies.items():
                            unique_deps = set(deps)
                            print(f'Module: {app}')
                            for dep in unique_deps:
                                print(f'  Group ID: {dep[0]}, Artifact ID: {dep[1]}, Version: {dep[2]}')
                            print()
                    else:
                        print(f"No dependencies found in project: {initial_directory}")
                        print()
                else:
                    print("Project root not found.")

if __name__ == '__main__':
    main()

'''


def main():
    initial_directory = r'H:\src_with_apk\MartinStyk_AndroidApkAnalyzer'
    output_path = os.path.join(initial_directory, 'label.txt')
    # 'F:\all_readme_src_apk\Excuser_1.2_APKPure\Excuser-master'
    # F:\all_readme_src_apk\India Satellite Weather_5.0.6_Apkpure\IndiaSatelliteWeather-master

    project_directory = find_project_root(initial_directory)
    if project_directory:
        dependencies, main_module_flag = scan_project_directory(project_directory)
        for app, deps in dependencies.items():
            unique_deps = set(deps)
            print(f'Module: {app}')
            for dep in unique_deps:
                print(f'  Group ID: {dep[0]}, Artifact ID: {dep[1]}, Version: {dep[2]}')
            print()

            if app == main_module_flag and not has_txt_file_in_current_directory(initial_directory):
                print("正在写入label")
                with open(output_path, 'w') as f:
                    for dep in unique_deps:
                        f.write(f"Group ID: {dep[0]}, Artifact ID: {dep[1]}, Version: {dep[2]}\n")
            elif app == main_module_flag and has_txt_file_in_current_directory(initial_directory):
                print("已经存在了label文件")


    else:
        print("Project root not found.")

# def main():
#     with open(r'D:/Pycoding/pycharm/F-droid-crawler/only_kts_1.txt', 'r') as file:
#         lines = file.readlines()  # 读取所有行
#     lines = [line.strip() for line in lines]
#     with open(r'D:/Pycoding/pycharm/F-droid-crawler/down.txt', 'r') as file:
#         lines_down = file.readlines()  # 读取所有行
#     lines_down = [line.strip() for line in lines_down]
#
#     for line in lines:
#         initial_directory = line.replace("H:/fdroid", "F:/all_fdroid")
#         clean_dir = line.removeprefix("H:/fdroid/")
#         output_path = os.path.join(initial_directory, 'label.txt')
#         if clean_dir in lines_down:
#             continue
#         # 'F:\all_readme_src_apk\Excuser_1.2_APKPure\Excuser-master'
#         # F:\all_readme_src_apk\India Satellite Weather_5.0.6_Apkpure\IndiaSatelliteWeather-master
#
#         project_directory = find_project_root(initial_directory)
#         if project_directory:
#             dependencies, main_module_flag = scan_project_directory(project_directory)
#             for app, deps in dependencies.items():
#                 unique_deps = set(deps)
#                 print(f'Module: {app}')
#                 for dep in unique_deps:
#                     print(f'  Group ID: {dep[0]}, Artifact ID: {dep[1]}, Version: {dep[2]}')
#                 print()
#                 if app == main_module_flag:
#                     with open(output_path, 'w') as f:
#                         for dep in unique_deps:
#                             f.write(f"Group ID: {dep[0]}, Artifact ID: {dep[1]}, Version: {dep[2]}\n")
#
#         else:
#             print("Project root not found.")

if __name__ == '__main__':
    main()


# F:\all_readme_src_apk\Buenos Aires Antes y Después_1.6.0.221_Apkpure\BuenosAiresAntesYDespues-master