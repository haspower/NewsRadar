# coding=utf-8
"""
自定义 AI 资讯解读 Agent 模块
提供可插拔的方式，通过配置目录中的自定义 Prompt 对资讯进行深度解读
"""

import os
from pathlib import Path
from typing import Any, Dict

from trendradar.ai.client import AIClient
from trendradar.ai.analyzer import AIAnalysisResult


class CustomAIAgent:
    """可插拔的自定义 AI 解读 Agent"""

    def __init__(self, ai_config: Dict[str, Any], prompt_dir: str = "config/custom/ai"):
        """
        初始化 Agent
        
        Args:
            ai_config: AI 模型配置（与原有配置格式一致）
            prompt_dir: 存放自定义 prompt 的目录路径
        """
        self.ai_config = ai_config
        self.prompt_dir = prompt_dir
        self.client = AIClient(ai_config)
    
    def _is_within_time_range(self, time_range_str: str) -> bool:
        """检查当前时间是否在指定范围内"""
        try:
            import datetime
            start_str, end_str = time_range_str.split('-')
            start_time = datetime.datetime.strptime(start_str.strip(), "%H:%M").time()
            end_time = datetime.datetime.strptime(end_str.strip(), "%H:%M").time()
            now_time = datetime.datetime.now().time()
            
            # 处理跨天情况 (如 23:00-07:00)
            if start_time <= end_time:
                return start_time <= now_time <= end_time
            else:
                return start_time <= now_time or now_time <= end_time
        except Exception as e:
            print(f"[CustomAgent] 时间范围格式解析错误 '{time_range_str}': {e}")
            return True # 解析失败默认放行

    def get_custom_prompts(self) -> Dict[str, str]:
        """
        获取目录下所有的自定义 prompt 文件，并过滤掉不在执行时间内的任务
        支持在文件开头使用 [TIME: 17:00-18:00] 格式进行时间过滤
        
        Returns:
            Dict[str, str]: {文件名标识: Prompt 内容}
        """
        import re
        base_dir = Path(__file__).parent.parent.parent / self.prompt_dir
        prompts = {}
        
        if not base_dir.exists():
            return prompts
            
        for file in base_dir.iterdir():
            if file.is_file() and file.suffix == '.txt':
                content = file.read_text(encoding="utf-8").strip()
                if not content:
                    continue
                
                # 检查第一行的的时间过滤标签
                lines = content.split('\n')
                first_line = lines[0].strip()
                time_match = re.search(r'^\[TIME:\s*([\d:]+\s*-\s*[\d:]+)\]', first_line, re.IGNORECASE)
                
                if time_match:
                    time_range = time_match.group(1)
                    if not self._is_within_time_range(time_range):
                        print(f"[CustomAgent] 当前时间不在 '{time_range}' 内，跳过执行: {file.name}")
                        continue
                    # 去除标签行
                    content = '\n'.join(lines[1:]).strip()
                    
                if content:
                    prompts[file.stem] = content
                    
        return prompts

    def run_custom_interpretations(self, base_result: AIAnalysisResult) -> None:
        """
        执行所有的自定义 prompt，并将结果补充到 base_result 中
        
        Args:
            base_result: 已完成基础分析的 AIAnalysisResult 对象
        """
        if not base_result.success:
            return

        prompts = self.get_custom_prompts()
        if not prompts:
            return
            
        if not self.client.api_key:
            print("[CustomAgent] 未配置 AI API Key，跳过自定义解读")
            return
            
        print(f"[CustomAgent] 检测到 {len(prompts)} 个自定义解读任务，开始执行...")
        
        # 提取当前 AI 分析的上下文供 Custom Agent 阅读
        context_parts = []
        if base_result.core_trends:
            context_parts.append(f"【核心热点态势】\n{base_result.core_trends}")
        if base_result.sentiment_controversy:
            context_parts.append(f"【舆论风向与争议】\n{base_result.sentiment_controversy}")
        if base_result.signals:
            context_parts.append(f"【异动与弱信号】\n{base_result.signals}")
        if base_result.outlook_strategy:
            context_parts.append(f"【研判与策略建议】\n{base_result.outlook_strategy}")
            
        context_text = "\n\n".join(context_parts)
        if not context_text:
            return

        for name, prompt_text in prompts.items():
            print(f"[CustomAgent] 正在运行自定义解读: {name}")
            try:
                # 组装最终提示词
                messages = [
                    {"role": "system", "content": prompt_text},
                    {"role": "user", "content": f"以下是今天的新闻热点AI分析结果，请根据要求进行解读：\n\n{context_text}"}
                ]
                
                response = self.client.chat(messages)
                if response:
                    base_result.custom_interpretations[name] = response.strip()
                    print(f"[CustomAgent] {name} 解读完成")
            except Exception as e:
                print(f"[CustomAgent] {name} 解读失败: {str(e)}")
