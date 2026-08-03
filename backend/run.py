import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    if os.environ.get('FLASK_DEBUG') == '1':
        # 本机调试模式：Flask 自带服务器 + 调试器，只绑定本机
        app.run(debug=True, host='127.0.0.1', port=5090)
    else:
        # 日常/生产运行：waitress 多线程 WSGI 服务器。
        # Flask 自带服务器默认一次只处理一个请求，访问量一上来所有人排队等同一个队列；
        # 且 debug=True 挂在 0.0.0.0 上等于向全内网开放远程执行代码的调试台。
        try:
            from waitress import serve
        except ImportError:
            raise SystemExit('缺少 waitress，请先安装：pip install waitress（已列入 requirements.txt）')
        print('Serving on http://0.0.0.0:5090 (waitress, 16 threads)')
        serve(app, host='0.0.0.0', port=5090, threads=16)
