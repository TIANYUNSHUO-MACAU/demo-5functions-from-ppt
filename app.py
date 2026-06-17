# ScholarAI - 学术极简智能助手 - 后端服务
# Python 3.11 + Flask

from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import os

# 注册蓝图
from routes.resume import resume_bp
from routes.copywriting import copywriting_bp
from routes.translate import translate_bp
from routes.pdf_summary import pdf_summary_bp
from routes.csv_preview import csv_preview_bp
from routes.config import config_bp
from routes.history import history_bp

app = Flask(__name__,
            template_folder='templates',
            static_folder='static')

# 跨域支持
CORS(app)

# 上传文件配置
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 最大16MB

# 注册路由蓝图
app.register_blueprint(resume_bp, url_prefix='/api/resume')
app.register_blueprint(copywriting_bp, url_prefix='/api/copywriting')
app.register_blueprint(translate_bp, url_prefix='/api/translate')
app.register_blueprint(pdf_summary_bp, url_prefix='/api/pdf')
app.register_blueprint(csv_preview_bp, url_prefix='/api/csv')
app.register_blueprint(config_bp, url_prefix='/api/config')
app.register_blueprint(history_bp, url_prefix='/api/history')


# 首页及工具页面路由均返回单页应用模版
@app.route('/')
@app.route('/resume')
@app.route('/copywriting')
@app.route('/translate')
@app.route('/pdf')
@app.route('/csv')
def index():
    """返回主页，单页前端入口"""
    return render_template('index.html')



# 健康检查
@app.route('/api/health')
def health():
    return jsonify({"status": "ok", "message": "ScholarAI 运行中"})


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5001)
