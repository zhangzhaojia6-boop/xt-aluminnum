export const mesWipSnapshotMock = {
  source: 'fallback',
  sourceLabel: 'MES截图口径 / 待正式对接',
  businessDate: '2026-04-27',
  updatedAt: '2026-04-27',
  summary: {
    monthlyContractTon: 6918,
    dailyContractTon: 0,
    monthlyFeedTon: 8955.2,
    dailyFeedTon: 49.5,
    wipTotalTon: 1148.5
  },
  feedByLine: [
    { line: '1450', ton: 0 },
    { line: '1650', ton: 0 },
    { line: '1850', ton: 0 },
    { line: '2050', ton: 49.5 }
  ],
  workshops: [
    { name: '1850车间', wipTon: 48.5, processes: [{ name: '冷轧', ton: 48.5 }] },
    { name: '2050车间', wipTon: 289.0, processes: [{ name: '冷轧', ton: 289.0 }] },
    { name: '拉矫车间', wipTon: 190.0, processes: [{ name: '洗拉', ton: 25.5 }, { name: '拉矫', ton: 70.5 }, { name: '退火', ton: 94.0 }] },
    { name: '热轧车间', wipTon: 25.5, processes: [{ name: '中厚板剪切', ton: 25.5 }] },
    { name: '精整', wipTon: 128.0, processes: [{ name: '剪切', ton: 30.0 }, { name: '纵剪', ton: 98.0 }] },
    { name: '新厂在线车间', wipTon: 305.0, processes: [{ name: '北线退火', ton: 305.0 }] },
    { name: '园区在线车间', wipTon: 96.5, processes: [{ name: '在线退火', ton: 96.5 }] },
    { name: '园区精整', wipTon: 66.0, processes: [{ name: '剪切', ton: 66.0 }] }
  ]
}
