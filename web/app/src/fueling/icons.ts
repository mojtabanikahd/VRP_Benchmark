import { copy } from "./copy"

const machineSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#14181c"/>
  <rect x="14" y="28" width="28" height="16" rx="3" fill="#f3efe6"/>
  <rect x="34" y="22" width="16" height="10" rx="2" fill="#c4622d"/>
  <circle cx="22" cy="48" r="5" fill="#f3efe6"/>
  <circle cx="40" cy="48" r="5" fill="#f3efe6"/>
  <rect x="18" y="16" width="6" height="14" rx="2" fill="#f3efe6"/>
</svg>`

const tankerSvg = `<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#14181c"/>
  <rect x="8" y="26" width="30" height="14" rx="4" fill="#c4622d"/>
  <rect x="38" y="30" width="16" height="10" rx="2" fill="#f3efe6"/>
  <circle cx="20" cy="46" r="5" fill="#f3efe6"/>
  <circle cx="46" cy="46" r="5" fill="#f3efe6"/>
</svg>`

export const MACHINE_ICON = `data:image/svg+xml,${encodeURIComponent(machineSvg)}`
export const TANKER_ICON = `data:image/svg+xml,${encodeURIComponent(tankerSvg)}`

export const MAX_IMAGE_BYTES = 200 * 1024

export function readImageFile(file: File): Promise<string> {
  if (!file.type.startsWith("image/")) {
    return Promise.reject(new Error(copy.imageFile))
  }
  if (file.size > MAX_IMAGE_BYTES) {
    return Promise.reject(new Error(copy.imageSize))
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = reader.result
      if (typeof result !== "string" || !result.startsWith("data:image/")) {
        reject(new Error(copy.imageRead))
        return
      }
      resolve(result)
    }
    reader.onerror = () => reject(new Error(copy.imageRead))
    reader.readAsDataURL(file)
  })
}
