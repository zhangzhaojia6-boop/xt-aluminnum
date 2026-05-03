(function () {
  const scriptUrl = 'https://g.alicdn.com/dingding/dingtalk-jsapi/2.10.3/dingtalk.open.js'

  window.loadDingTalkJsApi = function loadDingTalkJsApi() {
    if (window.dd) return Promise.resolve(window.dd)
    if (window.__dingtalkJsApiPromise) return window.__dingtalkJsApiPromise

    window.__dingtalkJsApiPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script')
      script.src = scriptUrl
      script.async = true
      script.onload = () => resolve(window.dd)
      script.onerror = () => reject(new Error('dingtalk_jsapi_load_failed'))
      document.head.appendChild(script)
    })

    return window.__dingtalkJsApiPromise
  }
}())
