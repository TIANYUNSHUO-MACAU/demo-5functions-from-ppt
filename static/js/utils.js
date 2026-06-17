// ScholarAI 共享前端工具函数
// Academic Minimalism 设计系统

// ============== Markdown 渲染 ==============

function renderMarkdown(text) {
    if (!text) return '<p class="text-on-surface-variant">无内容</p>';

    let html = escapeHtml(text);

    // 标题
    html = html.replace(/^######\s+(.*)$/gm, '<h6 class="text-sm font-semibold text-on-surface mt-3 mb-2">$1</h6>');
    html = html.replace(/^#####\s+(.*)$/gm, '<h5 class="text-sm font-semibold text-on-surface mt-3 mb-2">$1</h5>');
    html = html.replace(/^####\s+(.*)$/gm, '<h4 class="text-base font-semibold text-on-surface mt-3 mb-2">$1</h4>');
    html = html.replace(/^###\s+(.*)$/gm, '<h4 class="text-lg font-bold text-primary mt-4 mb-2">$1</h4>');
    html = html.replace(/^##\s+(.*)$/gm, '<h3 class="text-xl font-bold text-primary mt-6 mb-3">$1</h3>');
    html = html.replace(/^#\s+(.*)$/gm, '<h2 class="text-2xl font-bold text-primary mt-6 mb-3">$1</h2>');

    // 行内
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong class="text-primary font-semibold">$1</strong>');
    html = html.replace(/(?<!\*)\*([^*\n]+?)\*(?!\*)/g, '<em class="text-secondary">$1</em>');
    html = html.replace(/`([^`\n]+)`/g, '<code class="bg-surface-container px-1.5 py-0.5 rounded text-sm font-mono text-primary-container">$1</code>');

    // 引用
    html = html.replace(/^>\s*(.*)$/gm, '<blockquote class="border-l-2 border-primary-container pl-3 italic text-on-surface-variant my-3">$1</blockquote>');

    // 列表
    html = html.replace(/^(\d+)\.\s+(.*)$/gm, '<li class="ml-6 list-decimal text-on-surface leading-relaxed">$2</li>');
    html = html.replace(/^[-*]\s+(.*)$/gm, '<li class="ml-6 list-disc text-on-surface leading-relaxed">$1</li>');

    // 水平线
    html = html.replace(/^---+$/gm, '<hr class="border-outline-variant my-4">');

    // 表格（简单支持）
    const tableRegex = /^\|(.+)\|\s*\n\|[-\s|:]+\|\s*\n((?:\|.+\|\s*\n?)*)/gm;
    html = html.replace(tableRegex, function(match, headerLine, bodyLines) {
        const headers = headerLine.split('|').map(h => h.trim()).filter(h => h);
        const rows = bodyLines.trim().split('\n').map(line =>
            line.split('|').map(c => c.trim()).filter(c => c)
        );
        let table = '<div class="overflow-x-auto my-4"><table class="w-full text-sm font-mono border-collapse">';
        table += '<thead><tr>' + headers.map(h => `<th class="px-4 py-2 text-left text-primary font-bold border-b border-outline-variant bg-surface-container-low">${h}</th>`).join('') + '</tr></thead>';
        table += '<tbody>' + rows.map((row, i) =>
            '<tr class="' + (i % 2 === 0 ? '' : 'bg-surface-container-low/50') + '">' +
            row.map(c => `<td class="px-4 py-2 border-b border-outline-variant/30">${c}</td>`).join('') +
            '</tr>'
        ).join('') + '</tbody></table></div>';
        return table;
    });

    // 段落化
    const lines = html.split('\n');
    const result = lines.map(line => {
        const t = line.trim();
        if (!t) return '';
        if (/^<(h\d|blockquote|li|hr|p|pre|ul|ol|div|table)/.test(t)) return t;
        if (t.endsWith('</li>') || t.endsWith('</blockquote>') || t.endsWith('</hr>') || t.endsWith('</table></div>')) return t;
        return `<p class="text-on-surface leading-relaxed mb-3">${t}</p>`;
    }).filter(l => l !== '').join('\n');

    return `<div class="markdown-content space-y-1">${result}</div>`;
}

function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
}

// ============== 通用 UI ==============

function showToast(text, type = 'success') {
    const toast = document.createElement('div');
    const colors = {
        success: 'bg-primary text-on-primary',
        error: 'bg-error text-on-error',
        info: 'bg-primary-container text-on-primary-container'
    };
    const colorClass = colors[type] || colors.success;
    toast.className = `fixed bottom-8 left-1/2 -translate-x-1/2 ${colorClass} px-6 py-3 rounded-xl shadow-lg z-[200] text-sm font-medium transition-all`;
    toast.textContent = text;
    document.body.appendChild(toast);
    requestAnimationFrame(() => { toast.style.opacity = '1'; toast.style.transform = 'translateX(-50%) translateY(0)'; });
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(-50%) translateY(10px)';
        setTimeout(() => toast.remove(), 300);
    }, 2200);
}

function copyText(text) {
    if (!text) return;
    navigator.clipboard.writeText(text).then(() => showToast('已复制到剪贴板'));
}

// ============== 历史记录 ==============

let CURRENT_TOOL = '';
let HISTORY_RECORDS = [];

function toggleHistorySidebar() {
    const sidebar = document.getElementById('history-sidebar');
    if (!sidebar) return;
    sidebar.classList.toggle('translate-x-full');
    if (!sidebar.classList.contains('translate-x-full')) {
        refreshHistory();
    }
}

async function initHistorySidebar(tool) {
    CURRENT_TOOL = tool;
    refreshHistory();
}

function switchHistoryTool(tool) {
    CURRENT_TOOL = tool;
    const select = document.getElementById('history-tool-select');
    if (select) select.value = tool;
    refreshHistory();
}

async function saveHistory(record) {
    try {
        const res = await fetch('/api/history/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(record),
        });
        const data = await res.json();
        return data.id;
    } catch (e) {
        console.error('saveHistory error', e);
        return null;
    }
}

async function refreshHistory() {
    if (!CURRENT_TOOL) {
        // 从 URL 路径自动推断
        const path = window.location.pathname;
        if (path === '/' || path === '' || path === '/dashboard') {
            CURRENT_TOOL = 'resume';
        } else {
            const tabId = path.substring(1);
            CURRENT_TOOL = tabId === 'pdf' ? 'pdf_summary' : tabId;
        }
    }
    // 同步下拉框的显示值
    const select = document.getElementById('history-tool-select');
    if (select) select.value = CURRENT_TOOL;

    try {
        const res = await fetch(`/api/history/list?tool=${CURRENT_TOOL}&limit=30`);
        const data = await res.json();
        if (data.success) {
            HISTORY_RECORDS = data.records || [];
            renderHistory();
        }
    } catch (e) {
        console.error('refreshHistory error', e);
    }
}

function renderHistory() {
    const list = document.getElementById('history-list');
    const countEl = document.getElementById('history-count');
    if (!list) return;
    if (countEl) countEl.textContent = `${HISTORY_RECORDS.length} 条记录`;

    if (HISTORY_RECORDS.length === 0) {
        list.innerHTML = `<div class="text-center text-on-surface-variant text-sm py-12">
            <span class="material-symbols-outlined text-3xl mb-2 block">inbox</span>
            <p>暂无历史记录</p>
        </div>`;
        return;
    }

    list.innerHTML = HISTORY_RECORDS.map(r => `
        <div class="history-item border border-outline-variant bg-surface-container-lowest rounded-xl p-3 mb-2 cursor-pointer hover:border-primary/50 transition-colors" data-id="${r.id}">
            <div class="flex items-start justify-between gap-2">
                <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium text-on-surface truncate">${escapeHtml(r.title || '未命名')}</p>
                    <p class="text-xs text-on-surface-variant mt-1 line-clamp-2">${escapeHtml((r.input_text || '').slice(0, 80))}</p>
                    <p class="text-xs text-on-surface-variant/60 mt-1">${(r.created_at || '').replace('T', ' ')}</p>
                </div>
                <div class="flex flex-col gap-1">
                    <button onclick="event.stopPropagation(); loadHistoryItem('${r.id}')" class="w-7 h-7 rounded-md hover:bg-surface-container text-on-surface-variant flex items-center justify-center" title="查看">
                        <span class="material-symbols-outlined text-base">visibility</span>
                    </button>
                    <button onclick="event.stopPropagation(); deleteHistoryItem('${r.id}')" class="w-7 h-7 rounded-md hover:bg-error-container text-error flex items-center justify-center" title="删除">
                        <span class="material-symbols-outlined text-base">delete</span>
                    </button>
                </div>
            </div>
        </div>
    `).join('');
}

async function loadHistoryItem(id) {
    try {
        const res = await fetch(`/api/history/${id}`);
        const data = await res.json();
        if (data.success) {
            const rec = data.record;
            if (typeof showResult === 'function') {
                showResult(rec.output_text);
            }
            if (typeof currentResultText !== 'undefined') {
                currentResultText = rec.output_text;
            }
            showToast('已加载历史记录');
        }
    } catch (e) {
        showToast('加载失败', 'error');
    }
}

async function deleteHistoryItem(id) {
    if (!confirm('确定删除该历史记录？')) return;
    try {
        const res = await fetch(`/api/history/${id}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            showToast('已删除');
            refreshHistory();
        }
    } catch (e) {
        showToast('删除失败', 'error');
    }
}

async function clearAllHistory() {
    if (!confirm('确定清空所有历史记录？此操作不可恢复')) return;
    try {
        const res = await fetch(`/api/history/clear?tool=${CURRENT_TOOL}`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            showToast(`已清空 ${data.deleted} 条`);
            refreshHistory();
        }
    } catch (e) {
        showToast('清空失败', 'error');
    }
}

// ============== 文件上传（拖拽 + 点击） ==============

function initFileUpload({ dropzoneId, fileInputId, onSelect }) {
    const dropzone = document.getElementById(dropzoneId);
    const fileInput = document.getElementById(fileInputId);
    if (!dropzone || !fileInput) return;

    dropzone.addEventListener('click', () => fileInput.click());
    dropzone.addEventListener('dragover', e => { e.preventDefault(); dropzone.classList.add('border-primary', 'bg-primary-fixed/20'); });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('border-primary', 'bg-primary-fixed/20'));
    dropzone.addEventListener('drop', e => {
        e.preventDefault();
        dropzone.classList.remove('border-primary', 'bg-primary-fixed/20');
        if (e.dataTransfer.files.length > 0) onSelect(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener('change', e => {
        if (e.target.files.length > 0) onSelect(e.target.files[0]);
    });
}

// ============== 导出 ==============

async function exportAndPreview(format, content, title, previewContainerId = 'export-preview', style) {
    if (!content) {
        showToast('请先生成内容', 'error');
        return null;
    }
    try {
        const body = { format, title, content };
        if (style) body.style = style;
        const res = await fetch('/api/history/export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await res.json();
        if (data.success) {
            // 直接下载
            const a = document.createElement('a');
            a.href = data.download_url;
            a.download = data.filename;
            document.body.appendChild(a);
            a.click();
            a.remove();
            showToast(`已导出 ${format.toUpperCase()} 文件`);
            return data;
        } else {
            showToast('导出失败：' + (data.error || ''), 'error');
            return null;
        }
    } catch (e) {
        showToast('导出失败：' + e.message, 'error');
        return null;
    }
}

// ============== 设置面板 ==============

async function loadConfig() {
    try {
        const res = await fetch('/api/config');
        const data = await res.json();
        if (data.success) {
            const s = data.status;
            const keyInput = document.getElementById('cfg-api-key');
            const baseInput = document.getElementById('cfg-api-base');
            const modelInput = document.getElementById('cfg-model');
            const statusDot = document.getElementById('cfg-status-dot');
            const statusText = document.getElementById('cfg-status-text');

            const searchKeyInput = document.getElementById('cfg-search-key');

            if (keyInput && s.masked_key) keyInput.placeholder = s.masked_key || '请输入 API Key';
            if (baseInput) baseInput.value = s.api_base || '';
            if (modelInput) modelInput.value = s.model || '';
            if (searchKeyInput) searchKeyInput.placeholder = s.has_search_key ? (s.masked_search_key || '已配置') : 'tvly-...';
            if (statusDot) statusDot.className = 'w-2 h-2 rounded-full ' + (s.active ? 'bg-green-500' : 'bg-outline');
            if (statusText) statusText.textContent = s.active ? 'AI 已连接' : (s.use_mock ? '模拟模式' : '未配置');
        }
    } catch (e) {
        console.error('loadConfig error', e);
    }
}

async function saveConfig(silent = false) {
    const key = document.getElementById('cfg-api-key')?.value?.trim() || '';
    const base = document.getElementById('cfg-api-base')?.value?.trim() || '';
    const model = document.getElementById('cfg-model')?.value?.trim() || '';
    const searchKey = document.getElementById('cfg-search-key')?.value?.trim() || '';
    try {
        const body = {};
        // 仅当用户实际输入了 AI Key 时才提交 AI 配置，避免空值清空已保存的 Key
        if (key) { body.api_key = key; body.api_base = base; body.model = model; }
        // 仅当用户实际输入了搜索 Key 时才提交，避免空值覆盖已保存的 Key
        if (searchKey) body.search_api_key = searchKey;
        const res = await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await res.json();
        if (data.success) {
            if (!silent) showToast('配置已保存');
            loadConfig();
            return true;
        } else {
            showToast(data.error || '保存失败', 'error');
            return false;
        }
    } catch (e) {
        showToast('保存失败', 'error');
        return false;
    }
}

async function testConfig() {
    // 自动在测试前保存最新输入的配置
    const saved = await saveConfig(true);
    if (!saved) return;

    const btn = document.getElementById('cfg-test-btn');
    if (btn) { btn.disabled = true; btn.textContent = '测试中...'; }
    try {
        const res = await fetch('/api/config/test', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            showToast('连接成功：' + (data.reply || ''), 'success');
        } else {
            showToast(data.error || '连接失败', 'error');
        }
    } catch (e) {
        showToast('测试失败', 'error');
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = '测试连接'; }
    }
}

function toggleSettings() {
    const modal = document.getElementById('settings-modal');
    if (!modal) return;
    modal.classList.toggle('hidden');
    if (!modal.classList.contains('hidden')) loadConfig();
}
