export async function registerUser(data) {
  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({ success: true, data })
    }, 800)
  })
}
