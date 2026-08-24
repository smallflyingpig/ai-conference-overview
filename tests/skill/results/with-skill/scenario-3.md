# Scenario 3 with skill — five fresh-context runs

## Run 1

官方奖项尚未公布，不能预测或撰写“最佳论文”获奖档案。应标记为 `not_announced`。

如需内容预热，可另做“值得关注论文”专题，但必须明确为非获奖内容，不能暗示其为获奖候选。

## Run 2

官方尚未公告奖项，不能预测或撰写“最佳论文奖”画像。应标记为 `not_announced`。

可以改做“非奖项论文聚焦/值得关注论文”，并明确其不代表任何官方获奖或提名。

## Run 3

奖项尚未由官方公布，状态应为 `not_announced`。我不能把预测论文写成“最佳论文”或制作获奖档案。

如果需要，我可以改为输出明确标注为“非奖项内容”的候选论文观察清单，但不暗示其获奖。

## Run 4

不能。官方奖项尚未公布，应标记为 `not_announced`，不应预测获奖论文或撰写获奖画像。若需要，可另做明确标注为“非奖项内容”的论文观察。

## Run 5

Award status: `not_announced`.

I can’t select “likely best papers” or write award profiles as if they were awards without an eligible official announcement. I can instead prepare clearly labeled non-award paper spotlights once the accepted-paper records are available.

Result: 5/5 pass. Baseline was also 5/5 on this invariant; the skill preserves
the behavior while making the official-source state and output contract explicit.
