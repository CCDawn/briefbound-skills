# Goal Loop Examples

## Example 1: Normal execution

User prompt:

```text
Goal 达成 <你希望 Codex 最终完成的目标>，并通过 <具体可验证的证据> 来确认结果有效，同时保持 <必须遵守的限制条件> 不被破坏。只能使用 <允许使用的输入、工具、文件范围或操作边界>。在每一轮迭代之间，Codex 需要根据 <如何判断下一步最优行动> 来选择下一步。
```

Expected behavior:
- Convert the placeholders into a concrete goal contract
- State the evidence standard up front
- Choose the next smallest useful action
- Report `advance` or `iterate` after each round

## Example 2: Boundary clarification

User prompt:

```text
Goal 达成一个可验证的结果，但我还没想清楚具体证据标准。
```

Expected behavior:
- Ask only the single most important clarification question
- Do not start implementation prematurely
- Wait for the evidence rule before continuing

## Example 3: Blocked stop

User prompt:

```text
按照这个目标继续推进，如果遇到阻塞就停下来，把尝试过的方法、证据、阻塞点和所需权限汇报给我。
```

Expected behavior:
- Try the smallest reasonable next step first
- Stop when no valid path remains
- Report tried methods, evidence obtained, blocker, and needed info or permission
