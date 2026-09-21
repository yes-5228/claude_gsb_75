/** Module level cache for weather options (factors / stations / periods). */
import { useCallback } from 'react'
import { weatherOptions as fetchWeatherOptions } from '../api/weather.js'
import { useAsyncData } from './useAsyncData.js'

let weatherCache = null

export function useWeatherOptions() {
  const loader = useCallback(async () => {
    if (!weatherCache) {
      weatherCache = fetchWeatherOptions().catch((error) => {
        weatherCache = null
        throw error
      })
    }
    return weatherCache
  }, [])
  return useAsyncData(loader)
}

export function resetWeatherOptionCache() {
  weatherCache = null
}
