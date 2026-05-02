export const DEFAULT_ALLOY_GRADES = ['1060', '1100', '3003', '3004', '3105', '5052', '5083', '5754', '6061', '8011', '8079']

export async function loadCoilEntryStartup({ fetchMobileBootstrap, fetchCurrentShift, fetchFieldOptions }) {
  const [bootstrap, currentShift] = await Promise.all([
    fetchMobileBootstrap(),
    fetchCurrentShift(),
  ])

  let alloyGrades = DEFAULT_ALLOY_GRADES
  try {
    const grades = await fetchFieldOptions('alloy-grades')
    alloyGrades = Array.isArray(grades) && grades.length ? grades : DEFAULT_ALLOY_GRADES
  } catch {
    alloyGrades = DEFAULT_ALLOY_GRADES
  }

  return { bootstrap, currentShift, alloyGrades }
}
