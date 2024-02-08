import os

from flask import Flask, render_template


class Dashboard:
    def __init__(self):
        self.app = Flask(__name__)
        self.app.template_folder = os.path.join('templates')

        # 定义dashboard的路由
        @self.app.route('/')
        def index():
            # 在这个示例中，我们直接渲染了一个模板，你可以在这里加载任何你想要的dashboard内容
            return render_template('dashboard.html')

    def run(self):
        # 启动Flask应用
        self.app.run(use_reloader=False, use_debugger=False)


if __name__ == '__main__':
    dashboard = Dashboard()
    dashboard.run()
