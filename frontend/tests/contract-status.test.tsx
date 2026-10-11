import assert from 'node:assert/strict'
import { test } from 'node:test'
import { renderToStaticMarkup } from 'react-dom/server'
import ContractStatus from '../src/components/ContractStatus'

const cases = [
  { name: '科学计数法灰分上限不会显示假达标', standard: 1e-7, actual: 1, higherIsBetter: false, label: '超标' },
  { name: '科学计数法热值下限正确达标', standard: 1e-7, actual: 1, higherIsBetter: true, label: '达标' },
  { name: '零值上限保留数值语义', standard: 0, actual: 0, higherIsBetter: false, label: '达标' },
  { name: '正常百分数越界', standard: 18, actual: 19, higherIsBetter: false, label: '超标' },
  { name: '未提供合同不做判定', standard: null, actual: 1, higherIsBetter: false, label: '-' },
  { name: '缺失化验不按零值达标', standard: 18, actual: null, higherIsBetter: false, label: '-' },
]

for (const { name, label, ...props } of cases) {
  test(name, () => {
    const markup = renderToStaticMarkup(<ContractStatus {...props} />)
    assert.ok(markup.includes(`>${label}</span>`), markup)
    if (label === '-') assert.ok(!markup.includes('达标') && !markup.includes('超标'), markup)
  })
}
