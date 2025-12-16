import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

interface TimelineChartProps {
  data: Array<{
    timestamp: string;
    avg_response_time: number;
    request_count: number;
  }>;
}

export default function TimelineChart({ data }: TimelineChartProps) {
  const formattedData = data.map(item => ({
    time: new Date(item.timestamp).toLocaleTimeString(),
    'Tiempo Promedio (ms)': item.avg_response_time,
    'Requests': item.request_count,
  }));

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-xl font-bold text-gray-900 mb-4">
        Tiempo de Respuesta en el Tiempo
      </h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={formattedData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="time" />
          <YAxis />
          <Tooltip />
          <Legend />
          <Line 
            type="monotone" 
            dataKey="Tiempo Promedio (ms)" 
            stroke="#3b82f6" 
            strokeWidth={2}
            dot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
