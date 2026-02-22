/**
 * admin_chat_widget.js
 * 管理画面 AI チャットウィジェット (右下フローティング)
 */
(function() {
    'use strict';

    var CHAT_API = '/api/chat/admin/';
    var conversationHistory = [];
    var isOpen = false;

    function getCookie(name) {
        var value = '; ' + document.cookie;
        var parts = value.split('; ' + name + '=');
        if (parts.length === 2) return parts.pop().split(';').shift();
        return '';
    }

    function createWidget() {
        // Floating button
        var btn = document.createElement('button');
        btn.id = 'admin-chat-btn';
        btn.innerHTML = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>';
        btn.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:9999;width:56px;height:56px;border-radius:50%;background:var(--brand-primary,#465fff);color:#fff;border:none;cursor:pointer;box-shadow:0 4px 12px rgba(0,0,0,0.2);display:flex;align-items:center;justify-content:center;transition:transform 0.2s;';
        btn.title = 'AI アシスタント';
        btn.addEventListener('mouseenter', function() { btn.style.transform = 'scale(1.1)'; });
        btn.addEventListener('mouseleave', function() { btn.style.transform = 'scale(1)'; });
        btn.addEventListener('click', toggleChat);
        document.body.appendChild(btn);

        // Chat window
        var win = document.createElement('div');
        win.id = 'admin-chat-window';
        win.style.cssText = 'position:fixed;bottom:90px;right:24px;z-index:9999;width:360px;height:480px;background:#fff;border-radius:16px;box-shadow:0 8px 32px rgba(0,0,0,0.2);display:none;flex-direction:column;overflow:hidden;';
        win.innerHTML =
            '<div style="background:var(--brand-primary,#465fff);color:#fff;padding:14px 16px;font-weight:600;font-size:14px;display:flex;align-items:center;justify-content:space-between;">' +
                '<span>AI アシスタント</span>' +
                '<button id="admin-chat-close" style="background:none;border:none;color:#fff;cursor:pointer;font-size:18px;line-height:1;">&times;</button>' +
            '</div>' +
            '<div id="admin-chat-messages" style="flex:1;overflow-y:auto;padding:12px;font-size:13px;"></div>' +
            '<div style="padding:10px 12px;border-top:1px solid #e5e7eb;display:flex;gap:8px;">' +
                '<input id="admin-chat-input" type="text" placeholder="質問を入力..." style="flex:1;padding:8px 12px;border:1px solid #d1d5db;border-radius:8px;font-size:13px;outline:none;" />' +
                '<button id="admin-chat-send" style="background:var(--brand-primary,#465fff);color:#fff;border:none;border-radius:8px;padding:8px 14px;cursor:pointer;font-size:13px;font-weight:500;">送信</button>' +
            '</div>';
        document.body.appendChild(win);

        document.getElementById('admin-chat-close').addEventListener('click', toggleChat);
        document.getElementById('admin-chat-send').addEventListener('click', sendMessage);
        document.getElementById('admin-chat-input').addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
        });

        // Welcome message
        addMessage('assistant', 'こんにちは！管理画面の使い方について質問があればお気軽にどうぞ。');
    }

    function toggleChat() {
        isOpen = !isOpen;
        var win = document.getElementById('admin-chat-window');
        var btn = document.getElementById('admin-chat-btn');
        if (isOpen) {
            win.style.display = 'flex';
            btn.style.display = 'none';
            document.getElementById('admin-chat-input').focus();
        } else {
            win.style.display = 'none';
            btn.style.display = 'flex';
        }
    }

    function addMessage(role, text) {
        var container = document.getElementById('admin-chat-messages');
        var div = document.createElement('div');
        div.style.cssText = 'margin-bottom:10px;display:flex;' + (role === 'user' ? 'justify-content:flex-end;' : 'justify-content:flex-start;');
        var bubble = document.createElement('div');
        bubble.style.cssText = 'max-width:80%;padding:8px 12px;border-radius:12px;line-height:1.5;white-space:pre-wrap;word-break:break-word;' +
            (role === 'user'
                ? 'background:var(--brand-primary,#465fff);color:#fff;border-bottom-right-radius:4px;'
                : 'background:#f3f4f6;color:#333;border-bottom-left-radius:4px;');
        bubble.textContent = text;
        div.appendChild(bubble);
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
    }

    function sendMessage() {
        var input = document.getElementById('admin-chat-input');
        var message = input.value.trim();
        if (!message) return;

        input.value = '';
        addMessage('user', message);
        conversationHistory.push({ role: 'user', content: message });

        // Show loading
        var loadingId = 'loading-' + Date.now();
        var container = document.getElementById('admin-chat-messages');
        var loadDiv = document.createElement('div');
        loadDiv.id = loadingId;
        loadDiv.style.cssText = 'margin-bottom:10px;display:flex;justify-content:flex-start;';
        loadDiv.innerHTML = '<div style="padding:8px 12px;border-radius:12px;background:#f3f4f6;color:#999;font-size:12px;">考え中...</div>';
        container.appendChild(loadDiv);
        container.scrollTop = container.scrollHeight;

        fetch(CHAT_API, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify({ message: message, history: conversationHistory }),
        })
        .then(function(res) { return res.json(); })
        .then(function(data) {
            var el = document.getElementById(loadingId);
            if (el) el.remove();
            var reply = data.reply || data.error || 'エラーが発生しました。';
            addMessage('assistant', reply);
            conversationHistory.push({ role: 'assistant', content: reply });
        })
        .catch(function() {
            var el = document.getElementById(loadingId);
            if (el) el.remove();
            addMessage('assistant', '通信エラーが発生しました。');
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', createWidget);
    } else {
        createWidget();
    }
})();
