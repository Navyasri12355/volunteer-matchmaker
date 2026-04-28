export default function EventCard({ event }: any) {
  const severityColor = {
    CRITICAL: 'bg-red-100 border-red-400',
    MODERATE: 'bg-orange-100 border-orange-400',
    LOW: 'bg-yellow-100 border-yellow-400',
  };

  return (
    <div className={`border-2 rounded-lg p-4 ${severityColor[event.severity_band] || 'bg-gray-100'}`}>
      <h3 className="text-lg font-bold">{event.title}</h3>
      <p className="text-sm text-gray-600">{event.location_name}</p>
      <p className="text-sm mt-2">Category: {event.category}</p>
      <p className="text-sm">Severity: {event.severity_band}</p>
      <p className="text-sm">Score: {event.severity_score.toFixed(2)}</p>
      <p className="text-sm">Volunteers needed: {event.num_volunteers_needed}</p>
      <button className="mt-4 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700">
        View Details
      </button>
    </div>
  );
}
