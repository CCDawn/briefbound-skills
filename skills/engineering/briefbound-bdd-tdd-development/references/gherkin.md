# Gherkin 参考

只有在编写 `.feature` 文件或正式 BDD 场景时，才需要读这个文件。

## 核心关键字

- `Feature`：给能力命名。
- `Rule`：把多个场景归到一条业务规则下。
- `Background`：共享前置设置；谨慎使用。
- `Scenario`：一个具体例子。
- `Scenario Outline`：带 `Examples` 表格的模板场景。
- `Given`：前置条件。
- `When`：被测试的动作或事件。
- `Then`：预期且可观察到的结果。
- `And` / `But`：延续上一种步骤类型。

## 场景大纲

```gherkin
Scenario Outline: Invalid limits are rejected
  Given the supervised evolution workbench is open
  When the user enters case limit "<limit>"
  Then the workbench shows "<message>"

  Examples:
    | limit | message              |
    | -1    | limit must be >= 1   |
    | abc   | limit must be number |
```

只有当同一种行为会在多组取值上重复时，才使用 outline。如果这些例子本身承载的意义不同，就把它们拆成多个独立场景。

## 步骤质量检查表

- `When` 里只保留一个动作。
- 断言写在 `Then` 里。
- 优先使用领域语言，而不是实现名词。
- 保持场景彼此独立。
- 不要过早抽象可复用 step definitions，先让词汇表自然稳定下来。
