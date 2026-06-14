import psutil

def kill_celery_workers():
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == 'python.exe':
            try:
                proc.kill()  # 强制终止进程
                print(f"已终止进程: {proc.pid}")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

kill_celery_workers()