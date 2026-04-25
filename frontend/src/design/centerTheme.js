export const centerTheme = {
  entry: {
    label: '录入端',
    accent: '#0f6bff'
  },
  review: {
    label: '审阅端',
    accent: '#0f6bff'
  },
  admin: {
    label: '管理端',
    accent: '#0f6bff'
  },
  public: {
    label: '公共入口',
    accent: '#0f6bff'
  }
}

export function getCenterTheme(zone = 'review') {
  return centerTheme[zone] || centerTheme.review
}
