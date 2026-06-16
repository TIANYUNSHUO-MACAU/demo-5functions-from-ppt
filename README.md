# 多功能智能助手平台

一个网页入口 + 五个 AI 小工具，基于 Flask + DeepSeek API 构建。

## 功能模块

| 功能 | 入口路由 | API 前缀 | 核心能力 |
|------|---------|----------|----------|
| 简历优化 | `/resume` | `/api/resume` | 文本/文件上传、Markdown 渲染、简历内容拆分导出、历史记录 |
| 文案生成 | `/copywriting` | `/api/copywriting` | 多方案生成、分隔符清理、Markdown 渲染 |
| 翻译助手 | `/translate` | `/api/translate` | 中英互译 + 润色、文件上传 (PDF/Word/TXT) |
| PDF 摘要 | `/pdf` | `/api/pdf` | 文件上传、结构化摘要、Markdown 渲染 |
| CSV 预览 | `/csv` | `/api/csv` | Pandas 数据预览、数值统计、Markdown 分析报告 |

**全平台通用能力**：
- 所有工具支持历史记录（SQLite 持久化）
- 所有工具支持一键导出 Word / PDF（LaTeX 风格排版）
- 所有输出使用统一 Markdown 渲染器（标题分级、列表、引用、粗体）
- 右上角 API Key 配置面板（持久化到 `.env`）

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.11 / Flask / CORS |
| AI | OpenAI-compatible SDK（DeepSeek）|
| 文档解析 | pdfplumber / PyPDF2 / python-docx |
| 导出 | python-docx (Word) / reportlab (PDF, LaTeX 风格) |
| 数据存储 | SQLite（历史记录）|
| 前端 | HTML + Jinja2 模板 + Tailwind CSS + p5.js 粒子效果 |

## 快速开始

```bash
# 1. 创建虚拟环境
python3.11 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量（可选，不配则用模拟返回）
cp .env.example .env
# 编辑 .env 填入你的 DeepSeek API Key：
# AI_API_KEY=sk-xxxxxxxx
# AI_API_BASE=https://api.deepseek.com/v1
# AI_MODEL=deepseek-chat

# 4. 启动服务
python app.py

# 5. 浏览器访问
# http://localhost:5001
```

## 项目结构

```
ai-assistant-platform/
├── app.py                  # Flask 主入口（注册 7 个路由、配置上传目录）
├── requirements.txt        # 依赖清单
├── .env.example            # 环境变量模板（AI Key / API Base / Model）
├── data/                   # SQLite 数据库存放目录（运行时创建）
│
├── routes/                 # API 路由
│   ├── resume.py           # 简历优化：文本/文件双输入 + optimized_resume 字段
│   ├── copywriting.py      # 文案生成：多方案分隔符清理
│   ├── translate.py        # 翻译助手：翻译 + 润色双接口 + optimized_text
│   ├── pdf_summary.py      # PDF/Word/TXT 摘要
│   ├── csv_preview.py      # CSV Pandas 结构化预览 + 分析报告
│   ├── config.py           # 读取/测试/保存 API 配置（.env 持久化）
│   └── history.py          # 历史记录 CRUD + 导出 Word/PDF 接口
│
├── services/               # 服务层
│   ├── ai_service.py       # AI 调用统一服务（支持动态配置更新）
│   ├── doc_parser.py       # 统一文档解析：PDF/Word/TXT → 纯文本
│   ├── exporter.py         # Markdown → Word(Python-docx) / PDF(reportlab LaTeX 风格)
│   └── history_store.py    # SQLite 历史记录：save/list/get/delete/clear
│
├── templates/              # 前端 HTML 模板
│   ├── index.html          # 首页（工具卡片入口）
│   ├── resume.html         # 简历优化（文件上传 + 导出 + 历史侧栏）
│   ├── copywriting.html    # 文案生成
│   ├── translate.html      # 翻译助手（翻译/润色双模式）
│   ├── pdf.html            # PDF 摘要
│   ├── csv.html            # CSV 预览
│   ├── _settings_modal.html # 右上角 API Key 配置弹窗
│   └── _history_sidebar.html # 历史记录侧栏（每个工具页面复用）
│
└── static/                 # 静态资源
    ├── js/utils.js         # 通用工具函数（Markdown 渲染 / 文件上传 / 导出 / 历史记录）
    └── exports/            # 生成的 Word/PDF 文件临时存放
```

## API 文档

### 简历优化

**文本输入：**
```
POST /api/resume/optimize
Content-Type: application/json

请求：{ "text": "张三，前端工程师..." }
响应：{
  "success": true,
  "result": "## 一、问题与建议\n...\n\n## 二、优化后的简历\n...",
  "optimized_resume": "# 张三\n...",   // 仅简历内容，用于导出
  "input_text": "..."
}
```

**文件上传（PDF/Word/TXT）：**
```
POST /api/resume/optimize
Content-Type: multipart/form-data

请求：file=<简历文件>
响应：同上（自动提取文本后优化）
```

### 文案生成

```
POST /api/copywriting/generate
Content-Type: application/json

请求：{ "scene": "新品咖啡推广", "style": "年轻活力", "count": 3 }
响应：{
  "success": true,
  "result": "### 方案一：\n...\n\n### 方案二：\n..."
}
```

### 翻译助手

**翻译：**
```
POST /api/translate/translate
Content-Type: application/json 或 multipart/form-data

请求（文本）：{ "text": "Hello world", "target_lang": "中文" }
请求（文件）：file=<文档>, target_lang=English
响应：{
  "success": true,
  "result": "你好世界",
  "optimized_text": "你好世界",  // 用于导出
  "source": "Hello world",
  "target_lang": "中文"
}
```

**支持的目标语言**：`English`（英语）、`中文`、`日本語`（日语）、`한국어`（韩语）、`Français`（法语）、`Deutsch`（德语）、`Español`（西班牙语）、`Русский`（俄语）

**润色：**
```
POST /api/translate/polish
Content-Type: application/json

请求：{ "text": "需要润色的文本" }
响应：{ "success": true, "result": "润色后的文本", "optimized_text": "..." }
```

### PDF 摘要

```
POST /api/pdf/upload
Content-Type: multipart/form-data

请求：file=<PDF 或 Word 或 TXT 文件>
响应：{ "success": true, "result": "## 文档摘要\n...", "input_text": "..." }
```

### CSV 预览

```
POST /api/csv/upload
Content-Type: multipart/form-data

请求：file=<CSV 文件>
响应：{
  "success": true,
  "preview": { "columns": [...], "row_count": N, "col_count": M,
               "head": [...], "dtypes": {...}, "null_counts": {...}, "stats": {...} },
  "analysis": "## 数据分析报告\n..."
}
```

### 配置管理

```
GET  /api/config           # 获取当前配置状态（是否已配置 Key）
POST /api/config           # 保存 API Key / Base URL / Model 到 .env
POST /api/config/test      # 测试当前配置的 AI 连接
```

### 历史记录

```
POST /api/history/save     # 保存一条记录 { tool, title, input_text, output_text, meta }
GET  /api/history/list?tool=resume&limit=30  # 列出工具的历史记录
GET  /api/history/<id>     # 获取单条详情
DELETE /api/history/<id>   # 删除单条
POST /api/history/clear?tool=resume   # 清空某工具全部记录
POST /api/history/export   # 导出 Markdown → Word/PDF { format, title, content }
GET  /api/history/download/<path>     # 下载已生成的文档
```
