/**
 * Alist-Sync 前端JavaScript
 */

// 封装Ajax请求函数
function fetchApi(url, method = 'GET', data = null) {
    const options = {
        method: method,
        headers: {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
    };
    
    if (data && (method === 'POST' || method === 'PUT')) {
        options.body = JSON.stringify(data);
    }
    
    return fetch(url, options)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        });
}

// 显示通知
function showNotification(message, type = 'success') {
    // 检查是否已有通知容器
    let container = document.getElementById('notification-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'notification-container';
        container.style.position = 'fixed';
        container.style.top = '20px';
        container.style.right = '20px';
        container.style.zIndex = '9999';
        document.body.appendChild(container);
    }
    
    // 创建通知元素
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show`;
    notification.role = 'alert';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    
    // 添加到容器
    container.appendChild(notification);
    
    // 自动消失
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => {
            notification.remove();
        }, 150);
    }, 5000);
}

// 格式化时间戳
function formatTimestamp(timestamp) {
    if (!timestamp) return '从未';
    const date = new Date(timestamp * 1000);
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

// 格式化文件大小
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    
    return parseFloat((bytes / Math.pow(1024, i)).toFixed(2)) + ' ' + units[i];
}

// 加载动画
function showLoading(element) {
    element.innerHTML = '<div class="loading-spinner mx-auto"></div>';
}

function hideLoading(element, originalContent) {
    element.innerHTML = originalContent;
}

// 科技风格装饰
document.addEventListener('DOMContentLoaded', function() {
    // 为卡片添加科技风格边框
    document.querySelectorAll('.card').forEach(card => {
        card.classList.add('tech-border');
    });
    
    // 为表格添加悬停效果
    document.querySelectorAll('.table-hover tr').forEach(row => {
        row.addEventListener('mouseover', function() {
            this.style.backgroundColor = 'rgba(13, 110, 253, 0.1)';
        });
        
        row.addEventListener('mouseout', function() {
            this.style.backgroundColor = '';
        });
    });
    
    // 初始化工具提示
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
});

// 表单验证
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return false;
    
    let isValid = true;
    const requiredElements = form.querySelectorAll('[required]');
    
    requiredElements.forEach(element => {
        if (!element.value.trim()) {
            element.classList.add('is-invalid');
            isValid = false;
        } else {
            element.classList.remove('is-invalid');
        }
    });
    
    return isValid;
}

// 用于任务管理的函数
class TaskManager {
    constructor() {
        this.runningTasks = new Set();
    }
    
    startTask(taskId) {
        if (this.runningTasks.has(taskId)) {
            showNotification('任务已在运行中', 'warning');
            return false;
        }
        
        this.runningTasks.add(taskId);
        return true;
    }
    
    stopTask(taskId) {
        this.runningTasks.delete(taskId);
    }
    
    isTaskRunning(taskId) {
        return this.runningTasks.has(taskId);
    }
}

// 初始化任务管理器
const taskManager = new TaskManager();

// 表单提交前验证
document.addEventListener('DOMContentLoaded', function() {
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        const submitBtn = form.closest('.modal').querySelector('.btn-primary');
        if (submitBtn) {
            submitBtn.addEventListener('click', function(e) {
                const valid = validateForm(form.id);
                if (!valid) {
                    e.preventDefault();
                    showNotification('请填写所有必填字段', 'danger');
                }
            });
        }
    });
}); 