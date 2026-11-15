const restaurantDateFormatter = new Intl.DateTimeFormat('en', { timeZone: 'Asia/Tashkent', year: 'numeric', month: '2-digit', day: '2-digit' })

export function restaurantDate(timestamp) {
  const parts = restaurantDateFormatter.formatToParts(new Date(timestamp))
  const value = (type) => parts.find((part) => part.type === type).value
  return `${value('year')}-${value('month')}-${value('day')}`
}

export function filterOrders(orders, { status = 'all', search = '', dateFrom = '', dateTo = '' } = {}) {
  if (dateFrom && dateTo && dateFrom > dateTo) return []
  const keyword = search.trim().toLocaleLowerCase()
  const orderNumber = keyword.replace(/^#/, '')
  const numericId = /^\d+$/.test(orderNumber) ? Number(orderNumber) : null
  const phoneKeyword = keyword.replace(/[\s()\-]/g, '')
  return orders.filter((order) => {
    if (status === 'active' ? ['delivered', 'cancelled'].includes(order.status) : status !== 'all' && order.status !== status) return false
    if (dateFrom || dateTo) {
      const createdDate = restaurantDate(order.created_at)
      if (dateFrom && createdDate < dateFrom || dateTo && createdDate > dateTo) return false
    }
    if (!keyword) return true
    if (numericId !== null && order.id === numericId) return true
    const text = [order.address, order.phone, order.customer.name, ...order.items.map((item) => item.product_name)].join(' ').toLocaleLowerCase()
    return text.includes(keyword) || /^\+?\d{3,}$/.test(phoneKeyword) && order.phone.includes(phoneKeyword)
  })
}
