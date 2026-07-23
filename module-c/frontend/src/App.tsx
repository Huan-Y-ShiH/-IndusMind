import { Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import Dashboard from './pages/Dashboard';
import DeviceDetail from './pages/DeviceDetail';
import AlertCenter from './pages/AlertCenter';
import DiagnosisHistory from './pages/DiagnosisHistory';
import DiagnosisRecordView from './pages/DiagnosisRecordView';
import Settings from './pages/Settings';

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/device/:id" element={<DeviceDetail />} />
        <Route path="/alerts" element={<AlertCenter />} />
        <Route path="/history" element={<DiagnosisHistory />} />
        <Route path="/diagnosis/:recordId" element={<DiagnosisRecordView />} />
        <Route path="/settings" element={<Settings />} />
      </Routes>
    </Layout>
  );
}

export default App;
