import http, { toParams } from './client.js'

export const listWeather = (params) => http.get('/weather', { params: toParams(params) })
export const weatherOptions = () => http.get('/weather/options')
export const previewWeather = (payload) => http.post('/weather/preview', payload)
export const createObservation = (payload) => http.post('/weather/observations', payload)
export const deleteWeather = (id) => http.delete(`/weather/${id}`)
export const getCorrelation = (params) =>
  http.get('/weather/correlation', { params: toParams(params) })
export const exportWeatherUrl = (params) =>
  `/weather/export?${new URLSearchParams(toParams(params)).toString()}`
export const exportCorrelationUrl = (params) =>
  `/weather/correlation/export?${new URLSearchParams(toParams(params)).toString()}`
