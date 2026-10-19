                <!-- ==================================================== -->
                <!-- Interactive Streamlit Simulation Component (Joint Diagnosis) -->
                <!-- ==================================================== -->
                <div style="display: flex; flex-direction: column; gap: 15px; margin: 30px 0; font-family: 'Times New Roman', Times, serif;">
                    <div style="background: #e8f4f8; color: #0068c9; padding: 10px 15px; border-radius: 8px; font-size: 14px; font-weight: bold; text-align: center; border: 1px solid #0068c9;">
                        💡 Interactive Demo: Single sample split into two aliquots. Input both independent ADC signals to see the joint diagnosis.
                    </div>

                    <div style="display: flex; gap: 20px; justify-content: center; flex-wrap: wrap; text-align: left;">
                        <!-- Left: Input and Chart -->
                        <div style="flex: 1; min-width: 350px; max-width: 500px; border: 1px solid #ddd; border-radius: 12px; overflow: hidden; box-shadow: 0 6px 16px rgba(0,0,0,0.08); background: #fff; padding: 20px;">
                            <h4 style="margin-top: 0; color: #333;">🧪 Sample Measurements</h4>
                            
                            <div style="margin-bottom: 10px; font-size: 14px; font-weight: bold; color: #333;">Lactate Channel ADC (L4)</div>
                            <input type="number" id="adc-lac" value="800" style="width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; margin-bottom: 15px; box-sizing: border-box;">
                            
                            <div style="margin-bottom: 10px; font-size: 14px; font-weight: bold; color: #333;">Pyruvate Channel ADC (P2)</div>
                            <input type="number" id="adc-pyr" value="300" style="width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px; margin-bottom: 15px; box-sizing: border-box;">
                            
                            <button onclick="runJointDiagnosis()" style="width: 100%; background: #0068c9; color: white; border: none; padding: 10px; border-radius: 6px; font-size: 15px; font-weight: bold; cursor: pointer;">🩺 Run Joint Diagnosis</button>
                            
                            <div style="height: 220px; background: #fafafa; border: 1px dashed #ccc; border-radius: 6px; display: flex; align-items: center; justify-content: center; margin-top: 20px; position: relative;">
                                <canvas id="plot-canvas" width="420" height="220"></canvas>
                            </div>
                        </div>

                        <!-- Right: Result Card -->
                        <div style="flex: 1; min-width: 350px; max-width: 500px; border: 1px solid #ddd; border-radius: 12px; overflow: hidden; box-shadow: 0 6px 16px rgba(0,0,0,0.08); background: #fff; padding: 20px;">
                            <h4 style="margin-top: 0; color: #333;">📋 Diagnostic Result</h4>
                            
                            <div id="result-box" style="display: none; padding: 20px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); border-left: 6px solid #ccc; transition: all 0.3s ease;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                                    <div>
                                        <span style="font-size: 13px; color: #666;">Lactate (L4)</span>
                                        <div style="font-size: 24px; font-weight: bold; color: #0068c9;"><span id="res-lac">--</span> <span style="font-size: 14px; font-weight: normal;">mM</span></div>
                                    </div>
                                    <div>
                                        <span style="font-size: 13px; color: #666;">Pyruvate (P2)</span>
                                        <div style="font-size: 24px; font-weight: bold; color: #ff4b4b;"><span id="res-pyr">--</span> <span style="font-size: 14px; font-weight: normal;">μM</span></div>
                                    </div>
                                </div>
                                <hr style="margin: 10px 0;">
                                <div id="res-status" style="font-size: 22px; font-weight: bold; margin-bottom: 10px;">--</div>
                                <div id="res-note" style="font-size: 13px; color: #555; line-height: 1.4;">--</div>
                            </div>
                            <div id="placeholder-box" style="text-align: center; color: #999; margin-top: 50px;">
                                Run diagnosis to see results
                            </div>
                        </div>
                    </div>
                </div>
                <p class="hwmod-caption" style="text-align: center;">Fig. 17. Interactive simulation of the Streamlit interface for Dual-Probe Joint Diagnosis.</p>

                <!-- Simulation JS Script -->
                <script>
                (function() {
                    // 默认校准参数（模拟真实实验数据）
                    const l4_slope = 115.0;
                    const l4_int = 50.0;
                    const p2_slope = 1.5;
                    const p2_int = 40.0;

                    window.runJointDiagnosis = function() {
                        const adcLac = parseFloat(document.getElementById('adc-lac').value);
                        const adcPyr = parseFloat(document.getElementById('adc-pyr').value);
                        if (isNaN(adcLac) || isNaN(adcPyr)) return;

                        // 1. 计算浓度
                        const concLac = Math.max(0, (adcLac - l4_int) / l4_slope); // mM
                        const concPyr = Math.max(0, (adcPyr - p2_int) / p2_slope); // uM

                        // 2. 判断象限
                        let status, color, note;
                        if (concLac >= 5.0 && concPyr >= 200) {
                            status = "High Cancer Risk"; color = "#B91C1C";
                            note = "Warburg effect signature detected. Both biomarkers are synchronously elevated.";
                        } else if (concLac >= 5.0 && concPyr < 200) {
                            status = "Inflammation / Ischemia"; color = "#A86A1A";
                            note = "Lactate is elevated but pyruvate remains normal. Likely benign.";
                        } else if (concLac < 5.0 && concPyr >= 200) {
                            status = "High Pyruvate"; color = "#5A4A9A";
                            note = "Pyruvate is elevated but lactate is normal. Not typical of Warburg effect.";
                        } else {
                            status = "Normal"; color = "#2C6E4A";
                            note = "Both biomarkers are within normal ranges.";
                        }

                        // 3. 更新 UI 卡片
                        document.getElementById('placeholder-box').style.display = 'none';
                        const box = document.getElementById('result-box');
                        box.style.display = 'block';
                        box.style.borderLeftColor = color;
                        
                        document.getElementById('res-lac').innerText = concLac.toFixed(2);
                        document.getElementById('res-pyr').innerText = concPyr.toFixed(1);
                        
                        const statusEl = document.getElementById('res-status');
                        statusEl.innerText = status;
                        statusEl.style.color = color;
                        document.getElementById('res-note').innerText = note;

                        // 4. 绘制 Canvas 象限图
                        drawScatter(concPyr, concLac);
                    };

                    function drawScatter(pyr, lac) {
                        const canvas = document.getElementById('plot-canvas');
                        const ctx = canvas.getContext('2d');
                        const w = canvas.width, h = canvas.height;
                        const padL = 40, padB = 30, padR = 10, padT = 10;
                        const plotW = w - padL - padR;
                        const plotH = h - padT - padB;

                        ctx.clearRect(0, 0, w, h);

                        // 坐标轴映射 (X: 0-600 uM, Y: 0-25 mM)
                        function mapX(x) { return padL + (x / 600) * plotW; }
                        function mapY(y) { return h - padB - (y / 25) * plotH; }

                        // 画背景象限
                        // Normal (左下)
                        ctx.fillStyle = 'rgba(191, 227, 200, 0.5)';
                        ctx.fillRect(mapX(0), mapY(5), mapX(200)-mapX(0), mapY(0)-mapY(5));
                        // Inflammation (左上)
                        ctx.fillStyle = 'rgba(246, 217, 168, 0.5)';
                        ctx.fillRect(mapX(0), mapY(25), mapX(200)-mapX(0), mapY(5)-mapY(25));
                        // High Cancer (右上)
                        ctx.fillStyle = 'rgba(233, 184, 212, 0.5)';
                        ctx.fillRect(mapX(200), mapY(25), mapX(600)-mapX(200), mapY(5)-mapY(25));
                        // High Pyruvate (右下)
                        ctx.fillStyle = 'rgba(201, 196, 230, 0.5)';
                        ctx.fillRect(mapX(200), mapY(5), mapX(600)-mapX(200), mapY(0)-mapY(5));

                        // 画阈值线
                        ctx.strokeStyle = '#6A3AB2'; ctx.lineWidth = 1.5; ctx.setLineDash([5, 5]);
                        ctx.beginPath(); ctx.moveTo(mapX(200), padT); ctx.lineTo(mapX(200), h - padB); ctx.stroke();
                        ctx.beginPath(); ctx.moveTo(padL, mapY(5)); ctx.lineTo(w - padR, mapY(5)); ctx.stroke();
                        ctx.setLineDash([]);

                        // 画坐标轴和标签
                        ctx.strokeStyle = '#666'; ctx.lineWidth = 1;
                        ctx.beginPath(); ctx.moveTo(padL, padT); ctx.lineTo(padL, h-padB); ctx.lineTo(w-padR, h-padB); ctx.stroke();
                        
                        ctx.fillStyle = '#666'; ctx.font = '11px Arial'; ctx.textAlign = 'center';
                        ctx.fillText('Pyruvate (μM)', w/2, h-5);
                        ctx.save(); ctx.translate(12, h/2); ctx.rotate(-Math.PI/2); ctx.fillText('Lactate (mM)', 0, 0); ctx.restore();

                        // 画散点
                        const dotX = mapX(Math.min(pyr, 600));
                        const dotY = mapY(Math.min(lac, 25));
                        
                        ctx.beginPath(); ctx.arc(dotX, dotY, 8, 0, Math.PI*2);
                        
                        // 根据所在区域变色
                        if (lac >= 5 && pyr >= 200) ctx.fillStyle = '#B91C1C';
                        else if (lac >= 5 && pyr < 200) ctx.fillStyle = '#A86A1A';
                        else if (lac < 5 && pyr >= 200) ctx.fillStyle = '#5A4A9A';
                        else ctx.fillStyle = '#2C6E4A';

                        ctx.fill();
                        ctx.strokeStyle = '#fff'; ctx.lineWidth = 2; ctx.stroke();
                    }

                    // 页面加载后自动跑一次示例
                    window.addEventListener('DOMContentLoaded', () => {
                        setTimeout(window.runJointDiagnosis, 500);
                    });
                })();
                </script>
                <!-- ==================================================== -->
