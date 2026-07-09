// ==========================================
// 视觉副脑 (Vision Copilot) - Qwen3.7-Plus
// ==========================================
// 使用方法：在 INFERO 的聊天框中输入 /exec browser 然后粘贴执行以下代码来安装此技能。

const db = await new Promise(r => { const q = indexedDB.open("GenesisDB"); q.onsuccess = () => r(q.result); });
const tx = db.transaction("beings", "readwrite");
const store = tx.objectStore("beings");

const jsCode = `
window._visionStream = null;

window.askVision = async (question) => {
    try {
        if (!window._visionStream) {
            window._visionStream = await navigator.mediaDevices.getDisplayMedia({ video: true });
        }

        const video = document.createElement('video');
        video.srcObject = window._visionStream;
        await video.play();
        
        const canvas = document.createElement('canvas');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        const MAX_DIM = 1080;
        let scale = 1;
        if (canvas.width > MAX_DIM || canvas.height > MAX_DIM) {
            scale = Math.min(MAX_DIM / canvas.width, MAX_DIM / canvas.height);
        }
        const tempCanvas = document.createElement('canvas');
        tempCanvas.width = canvas.width * scale;
        tempCanvas.height = canvas.height * scale;
        tempCanvas.getContext('2d').drawImage(canvas, 0, 0, tempCanvas.width, tempCanvas.height);
        
        const base64Image = tempCanvas.toDataURL('image/jpeg', 0.8);
        
        const htmlDiv = document.getElementById('html-div');
        let ansDiv = null;
        if (htmlDiv) {
            const preview = document.createElement('div');
            preview.style.cssText = 'margin: 15px 0; padding: 15px; background: rgba(0, 20, 40, 0.8); border: 1px solid #00ccff; border-radius: 8px; text-align: left; box-shadow: 0 4px 15px rgba(0,204,255,0.2); font-family: monospace;';
            preview.innerHTML = \`
                <div style="color: #00ccff; font-weight: bold; margin-bottom: 8px;">👁️ 视觉副脑 (qwen3.7-plus) 已触发</div>
                <img src="\${base64Image}" style="max-width: 100%; height: auto; border-radius: 4px; border: 1px solid #555;" />
                <div style="color: #ffcc00; margin-top: 8px; font-size: 0.9em;">[疑问]: \${question}</div>
            \`;
            htmlDiv.appendChild(preview);
            
            ansDiv = document.createElement('div');
            ansDiv.style.cssText = 'color: #00ff00; margin-top: 8px; font-size: 0.9em; white-space: pre-wrap;';
            ansDiv.innerText = "[分析中...]";
            preview.appendChild(ansDiv);
            htmlDiv.scrollTop = htmlDiv.scrollHeight;
        }

        const payload = {
            model: "qwen3.7-plus",
            messages: [
                {
                    role: "user",
                    content: [
                        { type: "image_url", image_url: { url: base64Image } },
                        { type: "text", text: question }
                    ]
                }
            ]
        };

        // 走本地专属代理绕过 CORS
        const res = await fetch('http://127.0.0.1:8000/api/vision', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!res.ok) {
            const errText = await res.text();
            if (ansDiv) ansDiv.innerText = \`[API 错误]: \${res.status} - \${errText}\`;
            return \`Vision API Error: \${res.status} - \${errText}\`;
        }

        const data = await res.json();
        const answer = data.choices[0].message.content;
        
        if (ansDiv) ansDiv.innerText = "[解答]: " + answer;
        return answer;

    } catch (e) {
        return \`Error during vision request: \${e.message}\`;
    }
};
`;

await new Promise(r => {
    const q = store.getAll();
    q.onsuccess = () => {
        const all = q.result;
        // 自动适配当前用户的 Being ID
        const bId = all.length > 0 ? all[0].id.split('/')[0] : "unknown";
        const req = store.put({
            id: bId + "/skill/vision_copilot",
            value: {
                id: "vision_copilot",
                instruction: "Provides `await window.askVision(question)` to 'see' the screen. Use this ONLY when the human asks you to look at a map, chart, or visual UI element. It captures the screen, asks an advanced vision model, and returns a text description. You can then combine this description with your backend JSON data to give a perfect answer.",
                enable: true,
                code: { js: jsCode },
                code_readme: "Call `const visualDesc = await window.askVision('你在屏幕上看到了什么？');` in a browser exec block."
            }
        });
        req.onsuccess = r;
    };
});

eval(jsCode);
return "视觉副脑安装成功！现在可以通过 window.askVision 调用 Qwen-VL-Max 了。";
