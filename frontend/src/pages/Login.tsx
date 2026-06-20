import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Form, Input, Card, Typography, Alert } from 'antd';
import { Lock, Mail, Sparkles } from 'lucide-react';
import { useAuthStore } from '@/stores/authStore';

const { Title, Text } = Typography;

export const LoginPage = () => {
  const navigate = useNavigate();
  const { login, isAuthenticated, isLoading } = useAuthStore();
  const [form] = Form.useForm();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/');
    }
  }, [isAuthenticated, navigate]);

  const handleSubmit = async (values: { username: string; password: string }) => {
    setError(null);
    try {
      await login(values.username, values.password);
      navigate('/');
    } catch {
      setError('用户名或密码错误');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#1e3a5f] via-[#2d1b4e] to-[#1e3a5f] p-4">
      <div className="absolute inset-0 overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-[#667eea]/20 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-[#764ba2]/20 rounded-full blur-3xl" />
      </div>

      <Card className="w-full max-w-md bg-white/10 backdrop-blur-lg border-white/20 shadow-2xl">
        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-[#667eea] to-[#764ba2] flex items-center justify-center mb-4 shadow-lg">
            <Sparkles className="w-8 h-8 text-white" />
          </div>
          <Title level={3} className="text-white mb-2">
            AI全链路评测系统
          </Title>
          <Text className="text-white/60">请登录您的账户</Text>
        </div>

        {error && (
          <Alert
            message="登录失败"
            description={error}
            type="error"
            showIcon
            className="mb-6"
          />
        )}

        <Form
          form={form}
          onFinish={handleSubmit}
          layout="vertical"
          size="large"
        >
          <Form.Item
            name="username"
            label="用户名"
            rules={[{ required: true, message: '请输入用户名' }]}
          >
            <Input
              prefix={<Mail className="w-5 h-5 text-white/60" />}
              placeholder="请输入用户名"
              className="bg-white/10 border-white/20 text-white placeholder:text-white/40 focus:border-[#667eea] focus:ring-2 focus:ring-[#667eea]/20"
            />
          </Form.Item>

          <Form.Item
            name="password"
            label="密码"
            rules={[{ required: true, message: '请输入密码' }]}
          >
            <Input.Password
              prefix={<Lock className="w-5 h-5 text-white/60" />}
              placeholder="请输入密码"
              className="bg-white/10 border-white/20 text-white placeholder:text-white/40 focus:border-[#667eea] focus:ring-2 focus:ring-[#667eea]/20"
            />
          </Form.Item>

          <Form.Item className="flex justify-between mb-6">
            <Form.Item name="remember" valuePropName="checked" noStyle>
              <input type="checkbox" className="rounded border-white/20 text-[#667eea]" />
            </Form.Item>
            <span className="text-white/60 text-sm ml-2">记住我</span>
            <a href="#" className="text-white/60 text-sm hover:text-white">
              忘记密码?
            </a>
          </Form.Item>

          <Button
            type="primary"
            htmlType="submit"
            block
            loading={isLoading}
            className="h-12 bg-gradient-to-r from-[#667eea] to-[#764ba2] hover:from-[#5a67d8] hover:to-[#6b46c1] border-0 font-medium"
          >
            登录
          </Button>
        </Form>

        <div className="mt-6 text-center">
          <Text className="text-white/60 text-sm">
            还没有账户?{' '}
            <a href="#" className="text-[#667eea] hover:text-[#7c3aed]">
              联系管理员注册
            </a>
          </Text>
        </div>
      </Card>
    </div>
  );
};
