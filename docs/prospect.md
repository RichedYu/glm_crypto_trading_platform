# Prospect Roadmap · 优化展望

## Optimization Algorithms | 优化算法方向

1. **Adaptive Grid Search → 自适应网格搜索**  
   Use Bayesian Optimization on top of historical fills to auto-calibrate grid size, order spacing, and capital allocation.  
   利用贝叶斯优化在历史成交数据上自动校准网格宽度、挂单间距与资金分配比例。

2. **Risk-Aware Reinforcement Learning → 风险感知强化学习**  
   Train lightweight RL agents (e.g., PPO) constrained by drawdown and VaR ceilings to decide when to pause or resume trading.  
   以最大回撤、VaR 为约束，训练轻量级强化学习代理（如 PPO）来判断策略暂停与恢复时机。

3. **Multi-Objective Optimization → 多目标优化**  
   Frame profit, inventory risk, and liquidity cost as a Pareto frontier and select settings via evolutionary search.  
   将收益、库存风险、流动性成本构建为帕累托前沿，使用演化搜索挑选最优策略参数组合。

4. **Meta-Parameter Store → 元参数仓库**  
   Persist every backtest/production run’s parameter-performance pair so future optimizers start from proven regions.  
   将每次回测与实盘的“参数-收益”对写入元参数仓库，使后续优化从有效区域启动。

## Emotional Judgment | 情绪判断方向

1. **Multi-Source Sentiment Fusion → 多源情绪融合**  
   Blend Twitter, news, and on-chain chatter with attention-based weighting to avoid reliance on a single feed.  
   通过注意力权重融合推特、新闻、链上讨论，防止单一渠道失真。

2. **Context-Aware LLM Signals → 具备语境的 LLM 信号**  
   Use distilled domain LLMs to extract intent (FUD, governance, product launch) beyond simple positive/negative tags.  
   通过裁剪后的领域 LLM 提取情绪意图（FUD、治理、上新）而非单纯正负面标签。

3. **Sentiment Volatility Index → 情绪波动指数**  
   Track dispersion and kurtosis of sentiment streams; spikes trigger tighter risk caps.  
   统计情绪序列的离散度与峰度，剧烈波动即触发更严格的风控阈值。

4. **Feedback Loop with Strategy Service → 与策略服务的闭环反馈**  
   Push realized PnL back into the sentiment model to re-weight sources that truly predict returns.  
   将实盘收益回写至情绪模型，为准确预测收益的信源增加权重。

## Implementation Staging | 落地阶段

1. **Stage 1** – Introduce the API proxy pool & telemetry hooks to collect reliability data.  
   第一步：上线 API 代理池与监控埋点，收集可靠性数据。
2. **Stage 2** – Launch Bayesian optimizer for grid params and sentiment-volatility hybrid features.  
   第二步：启用网格参数贝叶斯优化，并构建情绪+波动混合特征。
3. **Stage 3** – Integrate reinforcement-learning guardrails and feedback-driven sentiment weighting.  
   第三步：引入强化学习风控，以及基于反馈的情绪权重更新。
