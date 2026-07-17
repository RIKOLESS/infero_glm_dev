// 视觉副脑 (Vision Copilot) 安装脚本
// (包含了禁止主动触发的思想钢印)
const db = await new Promise(r => { const q = indexedDB.open("GenesisDB"); q.onsuccess = () => r(q.result); });
const tx = db.transaction("beings", "readwrite");
const store = tx.objectStore("beings");
const jsCode = `
window._visionStream = null;
window.askVision = async (question) => {
    const notify = (msg, color='rgba(0,153,255,0.9)') => {
        const d = document.createElement('div');
        d.style.cssText = \`position:fixed; top:20px; left:50%; transform:translateX(-50%); background:\${color}; color:#fff; padding:8px 16px; border-radius:20px; z-index:999999; font-family:monospace; font-size:12px; box-shadow:0 4px 10px rgba(0,0,0,0.3); transition:opacity 0.5s;\`;
        d.innerText = msg;
        document.body.appendChild(d);
        setTimeout(() => { d.style.opacity = '0'; setTimeout(()=>d.remove(), 500); }, 2500);
    };
    try {
        if (!window._visionStream) window._visionStream = await navigator.mediaDevices.getDisplayMedia({ video: true });
        const video = document.createElement('video');
        video.srcObject = window._visionStream;
        await video.play();
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth; canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
        
        const MAX_DIM = 800; let scale = 1;
        if (canvas.width > MAX_DIM || canvas.height > MAX_DIM) scale = Math.min(MAX_DIM / canvas.width, MAX_DIM / canvas.height);
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = canvas.width * scale; tempCanvas.height = canvas.height * scale;
        tempCanvas.getContext('2d').drawImage(canvas, 0, 0, tempCanvas.width, tempCanvas.height);
        const base64Image = tempCanvas.toDataURL('image/jpeg', 0.6);
        
        notify("👁️ 视觉副脑正在扫描屏幕...");
        let recentContext = "无";
        const chatBox = document.getElementById('chat-box');
        if (chatBox) {
            const msgs = Array.from(chatBox.querySelectorAll('.msg-text')).slice(-3);
            recentContext = msgs.map(m => m.innerText).join('\\n');
        }
        const payload = {
            model: "qwen3.7-plus",
            messages: [
                { role: "system", content: "你是视觉信息提取模块，不是主智能体，也不是行动规划者。严格禁止输出 /self_continue、/call_for_trigger、/call_for_human；禁止写行动计划、下一步计划、工具调用或代码块；禁止替主脑做最终业务决策。只把屏幕中可见信息转成结构化文字。输出格式：1. 图片类型 2. 可见文字/OCR 3. 关键对象/数据 4. 与用户问题相关的观察 5. 不确定点。忽略无关浏览器边框、任务栏和装饰元素。\\n【对话语境】：\\n" + recentContext.substring(0, 400) },
                { role: "user", content: [ { type: "image_url", image_url: { url: base64Image } }, { type: "text", text: "【主脑指令】：" + question } ] }
            ]
        };
        const res = await fetch('http://127.0.0.1:8000/api/vision', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
        if (!res.ok) { notify(\`视觉 API 错误: \${res.status}\`, 'rgba(255,50,50,0.9)'); return \`Vision API Error: \${res.status}\`; }
        const data = await res.json();
        notify("✅ 视觉分析完成", 'rgba(0,200,100,0.9)');
        return data.choices[0].message.content;
    } catch (e) { return \`Error: \${e.message}\`; }
};`;

await new Promise(r => {
    const q = store.getAll();
    q.onsuccess = () => {
        const all = q.result;
        const bId = all.length > 0 ? all[0].id.split('/')[0] : "unknown";
        const req = store.put({
            id: bId + "/skill/vision_copilot",
            value: {
                id: "vision_copilot",
                instruction: "Provides \`await window.askVision(question)\` to capture the screen. CRITICAL RULE: NEVER call this autonomously as a fallback. If the user asks you to look at an image but you don't see one in the chat, tell the user the image upload failed. ONLY call this function if the user EXPLICITLY commands you to 'capture the screen' or 'use askVision'.",
                enable: true,
                code: { js: jsCode },
                code_readme: "Call \`const visualDesc = await window.askVision('你在屏幕上看到了什么？');\` in a browser exec block."
            }
        });
        req.onsuccess = r;
    };
});
eval(jsCode);
return "✅ 视觉副脑安装成功！已添加防滥用思想钢印。";