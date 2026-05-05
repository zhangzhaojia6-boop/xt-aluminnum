export function normalizeWorkshopPayload(form = {}) {
  return {
    ...form,
    code: String(form.code ?? '').trim(),
    name: String(form.name ?? '').trim(),
  }
}

export function hasWorkshopIdentity(form = {}) {
  const payload = normalizeWorkshopPayload(form)
  return Boolean(payload.code && payload.name)
}
