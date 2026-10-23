export const copy = {
  appTitle: "سوخت‌رسانی",
  eyebrow: "سوخت‌رسانی",
  scenario: "سناریو",
  defaultScenario: "سوخت‌رسانی بدون نام",
  machineTypes: "انواع ماشین",
  addMachineType: "افزودن نوع ماشین",
  machine: "ماشین",
  tanker: "تانکر",
  depot: "انبار",
  solver: "حل‌کننده",
  loadingSolvers: "در حال بارگذاری حل‌کننده‌ها…",
  catalogUnavailable: "فهرست حل‌کننده‌ها در دسترس نیست. سرویس را اجرا کنید و صفحه را تازه کنید.",
  timeBudget: "بودجهٔ زمانی",
  seed: "بذر",
  save: "ذخیره",
  load: "بارگذاری",
  undo: "واگرد",
  redo: "ازنو",
  reset: "بازنشانی",
  solve: "حل",
  solving: "در حال حل",
  tankCapacity: "ظرفیت مخزن (لیتر)",
  defaultFuel: "سوخت پیش‌فرض (لیتر)",
  defaultDuration: "مدت سوخت‌گیری پیش‌فرض (دقیقه)",
  removeType: "حذف نوع",
  replaceImage: "تعویض تصویر",
  details: "جزئیات",
  list: "فهرست",
  emptySelection: "برای ویرایش نام، میزان سوخت و پنجرهٔ سوخت‌گیری، یک انبار یا ماشین را انتخاب کنید.",
  remove: "حذف",
  name: "نام",
  shiftOpens: "شروع شیفت",
  shiftCloses: "پایان شیفت",
  machineType: "نوع ماشین",
  fuelDemand: "سوخت موردنیاز (لیتر)",
  windowOpens: "شروع پنجره",
  windowCloses: "پایان پنجره",
  duration: "مدت سوخت‌گیری (دقیقه)",
  setDepot: "تعیین انبار",
  placeMachine: "گذاشتن ماشین",
  select: "انتخاب",
  drivingDistance: "مسافت رانندگی",
  kilometers: "کیلومتر",
  feasible: "شدنی",
  infeasible: "نشدنی",
  emptySolution: "مسیر تانکرها پس از حل، روی خیابان‌هایی که می‌رانند، اینجا دیده می‌شود.",
  unnamedRoads: "خیابان‌های بدون نام",
  depart: "حرکت",
  return: "بازگشت",
  setTanker: "تانکر را مشخص کنید",
  wholeCapacity: "ظرفیت تانکر باید عدد صحیح لیتر باشد",
  placeDepot: "انبار را روی نقشه بگذارید",
  placeMachineIssue: "دست‌کم یک ماشین بگذارید",
  depotWindow: "شیفت انبار پیش از شروعش تمام می‌شود",
  chooseSolver: "حل‌کننده را انتخاب کنید",
  notFuelFile: "این پرونده یک سناریوی سوخت‌رسانی نیست",
  missingTanker: "نوع تانکر انتخاب‌شده در پرونده نیست",
  loadFailed: "این سناریو بارگذاری نشد",
  imageFile: "یک پروندهٔ تصویری انتخاب کنید",
  imageSize: "حجم تصویر باید ۲۰۰ کیلوبایت یا کمتر باشد",
  imageRead: "این تصویر خوانده نشد",
  imageRequired: "هر نوع به یک تصویر نیاز دارد",
  imageTooLarge: "یک تصویر بزرگ‌تر از ۲۰۰ کیلوبایت است",
  notReady: "سناریو آمادهٔ حل نیست",
  solverFailed: "حل‌کننده ناموفق بود",
}

export function machineName(index: number) {
  return `ماشین ${index}`
}

export function tankerLabel(index: number) {
  return `تانکر ${index}`
}

export function noMachineType(name: string) {
  return `${name} نوع ماشین ندارد`
}

export function windowOrder(name: string) {
  return `پنجرهٔ ${name} پیش از شروعش تمام می‌شود`
}

export function wholeFuel(name: string) {
  return `سوخت ${name} باید عدد صحیح لیتر باشد`
}

export function fuelExceedsTank(name: string) {
  return `سوخت ${name} از ظرفیت تانکر بیشتر است`
}

export function negativeDuration(name: string) {
  return `مدت سوخت‌گیری ${name} منفی است`
}

export function durationDoesNotFit(name: string) {
  return `مدت سوخت‌گیری ${name} در پنجره‌اش جا نمی‌شود`
}

export function missingType(name: string) {
  return `${name} به نوع ماشینی اشاره می‌کند که در پرونده نیست`
}

export function stopLabel(node: number) {
  return `توقف ${node}`
}

export function persianError(message: string): string {
  const text = message.trim()
  if (!text) return copy.solverFailed
  if (text.includes("refueling windows")) return "هیچ برنامه‌ای پنجرهٔ زمانی سوخت‌گیری را رعایت نمی‌کند"
  if (text.includes("does not fit")) return "مدت سوخت‌گیری در پنجرهٔ زمانی جا نمی‌شود"
  if (text.includes("tank capacity")) return "سوخت درخواستی از ظرفیت تانکر بیشتر است"
  if (text.includes("street path")) return "مسیر خیابان پیدا نشد"
  if (/no solution/i.test(text)) return "در این بودجهٔ زمانی جوابی پیدا نشد"
  if (text.includes("OSRM") || text.includes("driving route")) return "ارتباط با مسیریاب برقرار نشد"
  if (text.includes("not ready")) return copy.notReady
  if (text === "The solver failed") return copy.solverFailed
  return text
}
