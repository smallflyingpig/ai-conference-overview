export interface ConferenceAdvanceCopy {
  question: string;
  summary: string;
}

const conferenceAdvanceCopy: Record<string, ConferenceAdvanceCopy> = {
  "audited-evidence-text_llms": {
    question: "如何组织预训练上下文、提高长上下文效率、减少专项适配带来的能力损失，并解释模型内部机制？",
    summary: "文本模型的效果不只取决于模型规模，还受到预训练上下文、长文本计算效率、分阶段适配方法和内部机制的共同影响。",
  },
  "audited-evidence-multimodal_models": {
    question: "多模态系统如何同时处理组合概念、流式交互状态、结构化检索、评测偏差和跨模态安全问题？",
    summary: "多模态系统既要理解不同模态之间的组合关系，也要维持流式交互状态、使用结构化记忆，并抵御多种模态共同构成的攻击。",
  },
  "preliminary-examples-reasoning_agents": {
    question: "Agent 应如何协调任务规划、工具调用、记忆选择、浏览器状态、策略分支和停止条件？",
    summary: "Agent 需要把高层规划与具体执行结合起来，同时管理外部工具、长期状态、不同策略分支和停止时机。",
  },
  "audited-evidence-data_training": {
    question: "数据组织、PEFT 参数空间、RLVR 采样分布、批评反馈、熵权重和迭代重估会怎样共同影响训练？",
    summary: "训练效果既取决于语料组织方式，也取决于参数子空间的选择、采样分布的变化，以及模型反馈如何进入下一轮训练。",
  },
  "audited-evidence-evaluation_trust": {
    question: "面对数据污染、持续变化的任务分布、评测模型偏差、多模态攻击和记忆效应，如何让评测长期有效？",
    summary: "静态准确率会掩盖训练数据污染、评测模型偏差、多模态越狱、隐式记忆效应，以及模型在重复试验中的不一致表现。",
  },
};

export function conferenceAdvanceNarrative(
  advanceId: string,
): ConferenceAdvanceCopy | null {
  return conferenceAdvanceCopy[advanceId] ?? null;
}
