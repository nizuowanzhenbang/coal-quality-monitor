import { Tag } from 'antd'

interface Props {
  standard: number | null
  actual: number | null
  higherIsBetter: boolean
}

export default function ContractStatus({ standard, actual, higherIsBetter }: Props) {
  if (standard === null || actual === null || !Number.isFinite(standard) || !Number.isFinite(actual)) return <Tag>-</Tag>
  const satisfied = higherIsBetter ? actual >= standard : actual <= standard
  return <Tag color={satisfied ? 'green' : 'red'}>{satisfied ? '达标' : '超标'}</Tag>
}
