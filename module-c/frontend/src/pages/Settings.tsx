import React, { useEffect } from 'react';
import { Card, Form, Input, Button, Switch, Divider } from 'antd';
import { message } from 'antd';

/**
 * Settings — 系统设置页面 (暗夜工控风格)
 *
 * TODO:
 *   - API Token 配置（用于网关鉴权）
 *   - WebSocket 连接状态展示
 *   - 数据刷新间隔配置
 *   - 告警阈值配置
 */
const Settings: React.FC = () => {
  const [form] = Form.useForm();

  const handleSave = (values: Record<string, unknown>) => {
    if (typeof values.diagnoseApiKey === 'string') {
      localStorage.setItem('indusmind_diagnose_api_key', values.diagnoseApiKey);
    }
    message.success('Settings saved');
  };

  useEffect(() => {
    try {
      const key = localStorage.getItem('indusmind_diagnose_api_key');
      if (key) form.setFieldsValue({ diagnoseApiKey: key });
    } catch {}
  }, [form]);

  return (
    <div style={{ maxWidth: 700, margin: '0 auto' }}>
      <Card
        title={
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>
            ■ SYSTEM SETTINGS
          </span>
        }
      >
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            apiBaseUrl: 'http://localhost:8003',
            wsUrl: 'ws://localhost:8003/ws/alerts',
            refreshInterval: 5,
            alertSound: true,
            dashboardAutoRefresh: true,
          }}
          onFinish={handleSave}
        >
          <Divider orientation="left" plain>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>CONNECTION</span>
          </Divider>
          <Form.Item label="API Gateway URL" name="apiBaseUrl">
            <Input placeholder="http://localhost:8003" />
          </Form.Item>
          <Form.Item label="WebSocket URL" name="wsUrl">
            <Input placeholder="ws://localhost:8003/ws/alerts" />
          </Form.Item>
          <Form.Item label="API Token (Auth)" name="apiToken">
            <Input.Password placeholder="Leave blank to disable auth" />
          </Form.Item>
          <Form.Item label="Diagnose API Key" name="diagnoseApiKey">
            <Input.Password placeholder="Module B diagnose API key" />
          </Form.Item>

          <Divider orientation="left" plain>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11 }}>DISPLAY</span>
          </Divider>
          <Form.Item label="Refresh Interval (sec)" name="refreshInterval">
            <Input type="number" min={1} max={60} />
          </Form.Item>
          <Form.Item label="Dashboard Auto-Refresh" name="dashboardAutoRefresh" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item label="Alert Sound" name="alertSound" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit">SAVE SETTINGS</Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default Settings;
