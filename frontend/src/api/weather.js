import http, { toParams } from './client.js'

export const listWeather = (params) => http.get('/weather', { params: toParams(params) })
export const weatherContext = () => http.get('/weather/context')
export const createWeather = (payload) => http.post('/weather/entries', payload)
export const deleteWeather = (id) => http.delete(`/weather/${id}`)
export const correlation = (params) =>
  http.get('/weather/correlation', { params: toParams(params) })

export const exportWeatherUrl = (params) =>
  `/weather/export?${new URLSearchParams(toParams(params)).toString()}`
export const exportCorrelationUrl = (params) =>
  `/weather/correlation/export?${new URLSearchParams(toParams(params)).toString()}`
