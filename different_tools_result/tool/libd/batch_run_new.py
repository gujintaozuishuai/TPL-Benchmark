# -*- coding: utf-8 -*-  
import os
import subprocess
from tqdm import tqdm
import logging
import shutil
from multiprocessing import Pool

# 设置日志记录
logging.basicConfig(filename='batch_run_new_2.log', level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# 目标文件夹路径
base_path = '/home/gjt/Desktop/over_20_tpl_dataset_without_source'  # APK 文件所在的根目录
result_libd_path = './result_libd'  # 保存结果的文件夹

# 确保结果文件夹存在
if not os.path.exists(result_libd_path):
    os.makedirs(result_libd_path)

def process_apk(app_folder, file):
    apk_file_path = os.path.abspath(os.path.join(base_path, app_folder, file))
    
    # 参数二：格式为 result_libd/应用文件夹名%apk文件名%decompilation
    decomp_folder = os.path.join(result_libd_path, "{}%{}%decompilation".format(app_folder, file))
    # 参数三：格式为 result_libd/应用文件夹名%apk文件名%lib_info%libd.txt
    lib_info_file = os.path.join(result_libd_path, "{}%{}%lib_info%libd.txt".format(app_folder, file))
    # 结果保存路径：格式为 result_libd/应用文件夹名%apk文件名%run_info%libd.txt
    run_info_file = os.path.join(result_libd_path, "{}%{}%run_info%libd.txt".format(app_folder, file))

    # 检查是否已经存在所有结果文件
    if os.path.exists(decomp_folder) and os.path.exists(lib_info_file) and os.path.exists(run_info_file):
        logging.info("Skipping {} as all result files already exist.".format(apk_file_path))
        return  # 跳过已处理的 APK 文件

    # 如果部分文件已生成，删除已存在的文件
    if os.path.exists(decomp_folder):
        shutil.rmtree(decomp_folder)  # 删除整个文件夹及其内容
    if os.path.exists(lib_info_file):
        os.remove(lib_info_file)
    if os.path.exists(run_info_file):
        os.remove(run_info_file)

    # 确保输出文件夹存在
    if not os.path.exists(decomp_folder):
        os.makedirs(decomp_folder)

    # 构建命令
    command = [
        'python', 'libd_v_0.0.1.py', apk_file_path, decomp_folder, lib_info_file
    ]

    # 执行命令并将结果保存到对应的文件中
    try:
        with open(run_info_file, 'w') as result_file:
            result = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = result.communicate()
            
            result_file.write(stdout)
            result_file.write(stderr)  # 也记录 stderr
        logging.info("Executed for {}, result saved to {}".format(apk_file_path, run_info_file))
    except Exception as e:
        logging.error("Error executing for {}: {}".format(apk_file_path, e))

def process_app_folder(app_folder):
    app_folder_path = os.path.join(base_path, app_folder)
    
    if os.path.isdir(app_folder_path):  # 确保是文件夹
        # 遍历文件夹中的 APK 文件
        for file in os.listdir(app_folder_path):
            if file.endswith('.apk'):  # 只处理 .apk 文件
                process_apk(app_folder, file)

def main():
    # 获取所有应用文件夹列表
    app_folders = [f for f in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, f))]

    # 使用多进程处理每个应用文件夹
    pool = Pool(processes=4)  # 可根据实际情况调整进程数
    pool.map(process_app_folder, app_folders)

    logging.info("Batch execution completed.")

if __name__ == '__main__':
    main()

