# master views

本目录同时保留当前运行页和历史兼容页。

当前生产路由挂载这些页面：

- `Workshop.vue`：`/manage/master`
- `UserManagement.vue`：`/manage/admin/users`
- `WorkshopTemplateConfig.vue`：`/manage/admin/templates`
- `RuleConfigCenter.vue`：`/manage/admin/rules`
- `QRCodePrint.vue`：`/manage/admin/qr-print`
- `AliasMapping.vue`：`/manage/alias`

这些文件是历史兼容或静态契约参考，不挂载到生产路由：

- `Employee.vue`
- `Equipment.vue`
- `MachineWizard.vue`
- `ShiftConfig.vue`
- `Team.vue`

`/master/*` 旧入口保留为兼容路由，统一重定向到 `/manage/*` 的当前运行页。删除或迁移历史兼容页前，先同步仍读取这些文件的静态契约测试。
