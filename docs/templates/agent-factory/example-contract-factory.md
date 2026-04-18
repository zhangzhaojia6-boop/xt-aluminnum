# 合同自动汇总工厂样例（Example Contract Factory）

## 示例工作流
1. Historical intake 读取历史合同报表
2. 解析为 `ContractDailySnapshot`
3. 生成发布投影：`DailyReport.report_data.contract_lane`
4. 解析 `delivery_scope` 并路由到观察者 / 管理层
5. observer 控制台只读展示结果与异常

## 可复用替换规则
- 将“合同”替换为任意业务事实对象
- 将“车间/工厂”替换为任意业务作用域
- 将“WeCom”替换为任意交付通道

## 去铝业化检查
- 不依赖铝业专用字段名也能表达：输入 -> canonical -> projection -> delivery -> observer
