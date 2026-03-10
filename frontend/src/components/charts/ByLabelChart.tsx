import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface ByLabelChartProps {
  data: Array<{
    label: string;
    count: number;
    avg_time: number;
    min_time: number;
    max_time: number;
    success_count: number;
  }>;
}

export default function ByLabelChart({ data }: ByLabelChartProps) {
  const formattedData = data.map(item => ({
    name: item.label.length > 30 ? item.label.substring(0, 30) + '...' : item.label,
    'Tiempo Promedio (ms)': item.avg_time,
    'Total Requests': item.count,
  }));

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-3xl font-bold text-gray-900 mb-4">
        Tiempos por Endpoint
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={formattedData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="name" angle={-45} textAnchor="end" height={100} />
          <YAxis />
          <Tooltip />
          <Legend />
          <Bar dataKey="Tiempo Promedio (ms)" fill="#3b82f6" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
