import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import requests
import random
import json
from queue import Queue


class DeepSeekStressTester:
    def __init__(self, root):
        self.root = root
        self.root.title("DeepSeek API 压力测试工具 - 专业版")
        self.root.geometry("700x550")  # 增加窗口宽度
        self.root.resizable(False, False)

        self.api_key = ""
        self.is_testing = False
        self.thread_count = 5
        self.active_threads = 0
        self.threads = []
        self.token_length = 50  # 默认token长度

        # 线程安全的计数器
        self.request_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.counter_lock = threading.Lock()

        self.log_queue = Queue()

        self.setup_ui()
        self.update_log()

    def setup_ui(self):
        # API 密钥输入区域
        api_frame = ttk.LabelFrame(self.root, text="API 配置")
        api_frame.pack(padx=15, pady=10, fill="x")

        ttk.Label(api_frame, text="DeepSeek API Key:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.api_entry = ttk.Entry(api_frame, width=60)  # 增加宽度
        self.api_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew", columnspan=2)

        # 并发设置区域
        concurrency_frame = ttk.LabelFrame(self.root, text="并发设置")
        concurrency_frame.pack(padx=15, pady=5, fill="x")

        ttk.Label(concurrency_frame, text="并发线程数:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.thread_spinbox = ttk.Spinbox(concurrency_frame, from_=1, to=100, width=5)
        self.thread_spinbox.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.thread_spinbox.set(5)

        ttk.Label(concurrency_frame, text="(1-100)").grid(row=0, column=2, padx=5, pady=5, sticky="w")

        # 请求设置区域
        request_frame = ttk.LabelFrame(self.root, text="请求设置")
        request_frame.pack(padx=15, pady=5, fill="x")

        # 请求长度选择
        ttk.Label(request_frame, text="请求长度:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.token_var = tk.StringVar(value="50 tokens")
        token_options = ["10 tokens (短文本)", "20 tokens (中等文本)", "50 tokens (标准文本)", "100 tokens (长文本)"]
        self.token_combobox = ttk.Combobox(request_frame, textvariable=self.token_var,
                                           values=token_options, state="readonly", width=25)
        self.token_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # 模型选择
        ttk.Label(request_frame, text="模型:").grid(row=0, column=2, padx=(15, 5), pady=5, sticky="w")
        self.model_var = tk.StringVar(value="deepseek-chat")
        model_options = ["deepseek-chat", "deepseek-coder"]
        self.model_combobox = ttk.Combobox(request_frame, textvariable=self.model_var,
                                           values=model_options, state="readonly", width=15)
        self.model_combobox.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        # 测试控制区域
        control_frame = ttk.LabelFrame(self.root, text="测试控制")
        control_frame.pack(padx=15, pady=5, fill="x")

        self.start_btn = ttk.Button(control_frame, text="开始测试", command=self.start_test)
        self.start_btn.grid(row=0, column=0, padx=5, pady=10)

        self.stop_btn = ttk.Button(control_frame, text="停止测试", command=self.stop_test, state=tk.DISABLED)
        self.stop_btn.grid(row=0, column=1, padx=5, pady=10)

        # 统计信息区域
        stats_frame = ttk.LabelFrame(self.root, text="测试统计")
        stats_frame.pack(padx=15, pady=5, fill="x")

        stats_labels = ["总请求数:", "成功请求:", "失败请求:", "活动线程数:", "当前状态:", "平均响应时间:"]
        self.stats_vars = [tk.StringVar() for _ in range(6)]
        self.stats_vars[5].set("0.00s")  # 平均响应时间初始值

        for i, label in enumerate(stats_labels):
            ttk.Label(stats_frame, text=label).grid(row=i // 2, column=(i % 2) * 2, padx=5, pady=2, sticky="w")
            ttk.Label(stats_frame, textvariable=self.stats_vars[i]).grid(row=i // 2, column=(i % 2) * 2 + 1, padx=5,
                                                                         pady=2, sticky="w")

        # 设置初始值
        self.stats_vars[0].set("0")
        self.stats_vars[1].set("0")
        self.stats_vars[2].set("0")
        self.stats_vars[3].set("0")
        self.stats_vars[4].set("等待开始")

        # 日志区域
        log_frame = ttk.LabelFrame(self.root, text="实时日志")
        log_frame.pack(padx=15, pady=10, fill="both", expand=True)

        self.log_text = tk.Text(log_frame, height=14, state=tk.DISABLED)  # 增加高度
        self.log_text.pack(padx=5, pady=5, fill="both", expand=True)

        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

    def log_message(self, message):
        self.log_queue.put(message)

    def update_log(self):
        while not self.log_queue.empty():
            message = self.log_queue.get()
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, message + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        self.root.after(100, self.update_log)

    def update_stats(self):
        self.stats_vars[0].set(str(self.request_count))
        self.stats_vars[1].set(str(self.success_count))
        self.stats_vars[2].set(str(self.failure_count))
        self.stats_vars[3].set(str(self.active_threads))

        # 计算平均响应时间（仅当有成功请求时）
        if self.success_count > 0 and hasattr(self, 'total_response_time'):
            avg_time = self.total_response_time / self.success_count
            self.stats_vars[5].set(f"{avg_time:.2f}s")

    def start_test(self):
        self.api_key = self.api_entry.get().strip()
        if not self.api_key:
            messagebox.showerror("错误", "请输入有效的API密钥")
            return

        try:
            self.thread_count = int(self.thread_spinbox.get())
            if self.thread_count < 1 or self.thread_count > 100:
                raise ValueError
        except ValueError:
            messagebox.showerror("错误", "请输入1-100之间的有效线程数")
            return

        # 根据选择的token长度设置值
        token_choice = self.token_var.get()
        if token_choice == "10 tokens (短文本)":
            self.token_length = 10
        elif token_choice == "20 tokens (中等文本)":
            self.token_length = 20
        elif token_choice == "50 tokens (标准文本)":
            self.token_length = 50
        elif token_choice == "100 tokens (长文本)":
            self.token_length = 100
        else:
            self.token_length = 50  # 默认值

        self.is_testing = True
        self.request_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.active_threads = 0
        self.threads = []
        self.total_response_time = 0.0  # 用于计算平均响应时间

        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.stats_vars[4].set("测试运行中...")
        self.stats_vars[5].set("0.00s")  # 重置平均响应时间

        self.log_message("=== 开始压力测试 ===")
        self.log_message(f"使用API密钥: {self.api_key[:8]}****{self.api_key[-4:]}")
        self.log_message(f"启动 {self.thread_count} 个并发线程...")
        self.log_message(f"请求长度: {token_choice}")
        self.log_message(f"使用模型: {self.model_var.get()}")

        # 启动多个测试线程
        for i in range(self.thread_count):
            thread = threading.Thread(target=self.run_stress_test, args=(i + 1,), daemon=True)
            thread.start()
            self.threads.append(thread)
            self.active_threads += 1
            self.update_stats()

    def stop_test(self):
        self.is_testing = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.stats_vars[4].set("测试已停止")
        self.log_message("=== 测试已停止 ===")
        self.log_message(f"等待工作线程结束...")

        # 等待所有线程结束
        for thread in self.threads:
            thread.join(timeout=1.0)

        self.active_threads = 0
        self.update_stats()
        self.log_message("所有工作线程已停止")

    def get_prompt_template(self, token_length):
        """根据token长度返回不同的提示模板"""
        if token_length <= 20:
            # 短文本模板
            subjects = ["人工智能", "机器学习", "深度学习", "神经网络"]
            verbs = ["研究", "应用", "开发", "优化"]
            objects = ["模型", "算法", "系统", "框架"]
            return f"{random.choice(subjects)}如何{random.choice(verbs)}在{random.choice(objects)}中？"

        elif token_length <= 50:
            # 中等文本模板
            topics = [
                "请解释机器学习和深度学习的区别",
                "什么是神经网络？它如何工作？",
                "自然语言处理的主要应用有哪些？",
                "计算机视觉在工业中有哪些实际应用？"
            ]
            return random.choice(topics)

        else:
            # 长文本模板
            detailed_topics = [
                "请详细解释Transformer架构在自然语言处理中的作用，包括自注意力机制、编码器-解码器结构以及其在现代大型语言模型中的应用。",
                "讨论人工智能在医疗领域的应用，包括医学影像分析、药物发现和个性化医疗等方面，并分析其面临的挑战和未来发展趋势。",
                "解释强化学习的基本原理，包括马尔可夫决策过程、奖励函数、价值函数和策略优化等概念，并举例说明其在游戏AI和机器人控制中的应用。",
                "请详细描述云计算、边缘计算和物联网之间的关系，以及它们如何共同推动现代智能系统的发展，包括实际应用案例和技术挑战。"
            ]
            return random.choice(detailed_topics)

    def run_stress_test(self, thread_id):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 词汇库
        vocab = ["人工智能", "机器学习", "深度学习", "神经网络", "自然语言处理",
                 "计算机视觉", "大数据", "算法优化", "模型训练", "压力测试",
                 "API性能", "分布式系统", "高并发", "响应时间", "吞吐量",
                 "Python", "Java", "C++", "JavaScript", "Golang",
                 "云计算", "边缘计算", "物联网", "区块链", "网络安全",
                 "数据结构", "算法分析", "操作系统", "数据库", "软件工程",
                 "前端开发", "后端开发", "全栈开发", "DevOps", "微服务",
                 "容器化", "Kubernetes", "Docker", "CI/CD", "自动化测试",
                 "性能优化", "内存管理", "多线程", "并发编程", "异步IO",
                 "机器学习", "深度学习", "强化学习", "迁移学习", "生成对抗网络",
                 "计算机视觉", "图像识别", "目标检测", "语义分割", "OCR",
                 "自然语言处理", "文本分类", "情感分析", "机器翻译", "命名实体识别",
                 "语音识别", "语音合成", "语音助手", "对话系统", "聊天机器人",
                 "推荐系统", "协同过滤", "内容推荐", "个性化推荐", "广告推荐",
                 "大数据", "Hadoop", "Spark", "Flink", "数据仓库",
                 "数据挖掘", "数据分析", "数据可视化", "商业智能", "数据科学",
                 "云计算", "AWS", "Azure", "GCP", "阿里云",
                 "边缘计算", "物联网", "传感器网络", "智能家居", "工业互联网",
                 "区块链", "比特币", "以太坊", "智能合约", "去中心化应用",
                 "网络安全", "加密算法", "防火墙", "入侵检测", "渗透测试"]

        self.log_message(f"线程 #{thread_id}: 已启动 | 请求长度: {self.token_length}tokens")

        while self.is_testing:
            try:
                # 根据token长度生成不同的请求内容
                if self.token_length <= 20:
                    # 短文本：使用模板
                    prompt = self.get_prompt_template(self.token_length)
                    word_count = random.randint(5, 8)  # 短文本词数
                elif self.token_length <= 50:
                    # 中等文本：混合模板和随机词汇
                    if random.random() > 0.3:
                        prompt = self.get_prompt_template(self.token_length)
                    else:
                        prompt = " ".join(random.choices(vocab, k=random.randint(8, 12)))
                    word_count = random.randint(8, 15)
                else:
                    # 长文本：主要使用模板
                    prompt = self.get_prompt_template(self.token_length)
                    word_count = random.randint(15, 25)

                payload = {
                    "model": self.model_var.get(),
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": self.token_length,
                    "temperature": random.uniform(0.5, 1.2)
                }

                # 发送API请求 - 修复括号问题
                start_time = time.time()
                response = requests.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers=headers,
                    data=json.dumps(payload)
                )  # 添加了缺失的右括号
                elapsed = time.time() - start_time

                # 使用锁安全更新计数器
                with self.counter_lock:
                    self.request_count += 1

                    if response.status_code == 200:
                        self.success_count += 1
                        self.total_response_time += elapsed  # 累加响应时间
                    else:
                        self.failure_count += 1

                # 更新日志（线程安全）
                if response.status_code == 200:
                    self.log_message(
                        f"线程 #{thread_id} - 成功 | 长度: {self.token_length}tokens | 耗时: {elapsed:.2f}s")
                else:
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("error", {}).get("message", "未知错误")
                    except json.JSONDecodeError:
                        error_msg = "无法解析错误响应"
                    self.log_message(
                        f"线程 #{thread_id} - 失败 | 长度: {self.token_length}tokens | 状态码: {response.status_code} | 错误: {error_msg}")

                # 更新统计信息
                self.update_stats()

                # 根据token长度调整请求间隔
                if self.token_length <= 20:
                    sleep_time = random.uniform(0.1, 0.3)  # 短文本快速请求
                elif self.token_length <= 50:
                    sleep_time = random.uniform(0.2, 0.5)  # 中等文本中等速度
                else:
                    sleep_time = random.uniform(0.3, 1.0)  # 长文本慢速请求

                time.sleep(sleep_time)

            except Exception as e:
                with self.counter_lock:
                    self.failure_count += 1
                self.log_message(f"线程 #{thread_id} - 异常: {str(e)}")
                self.update_stats()
                time.sleep(1)

        self.log_message(f"线程 #{thread_id}: 已停止")
        with self.counter_lock:
            self.active_threads -= 1
        self.update_stats()


if __name__ == "__main__":
    root = tk.Tk()
    app = DeepSeekStressTester(root)
    root.mainloop()
