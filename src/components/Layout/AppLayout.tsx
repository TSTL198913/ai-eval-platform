
import React from 'react';
import { Layout, Menu, Avatar, Dropdown, Button, Typography } from 'antd';
import { 
  LayoutDashboard, 
  Settings2, 
  BarChart3, 
  FileText, 
  DollarSign, 
  Activity, 
  LogOut,
  User,
  ChevronDown
} from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import useAuthStore from '../stores/authStore';

const { Header, Sider, Content } = Layout;
const { Title } = Typography;

const menuItems = [
  { key: '/', icon: <LayoutDashboard className='w-5 h-5' />, label: '仪表盘' },
  { key: '/evaluators', icon: <Settings2 className='w-5 h-5' />, label: '评估器管理' },
  { key: '/models', icon: <BarChart3 className='w-5 h-5' />, label: '模型对比' },
  { key: '/records', icon: <FileText className='w-5 h-5' />, label: '评估记录' },
  { key: '/cost', icon: <DollarSign className='w-5 h-5' />, label: '成本监控' },
  { key: '/health', icon: <Activity className='w-5 h-5' />, label: '系统健康' },
];

interface LayoutProps {
  children: React.ReactNode;
}

const AppLayout: React.FC<LayoutProps> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const logout = useAuthStore((state) => state.logout);

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key);
  };

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const userMenu = (
    <Menu>
      <Menu.Item key='profile' icon={<User className='w-4 h-4' />}>个人资料</Menu.Item>
      <Menu.Item key='logout' icon={<LogOut className='w-4 h-4' />} onClick={handleLogout}>退出登录</Menu.Item>
    </Menu>
  );

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider 
        theme='dark' 
        width={250} 
        style={{ 
          background: 'linear-gradient(180deg, #1e3a5f 0%, #2d1b69 100%)',
          boxShadow: '2px 0 20px rgba(0,0,0,0.1)'
        }}
      >
        <div className='p-6 text-center'>
          <div className='w-12 h-12 mx-auto mb-3 bg-gradient-to-r from-blue-500 to-purple-500 rounded-xl flex items-center justify-center'>
            <Settings2 className='w-6 h-6 text-white' />
          </div>
          <Title level={4} className='text-white mb-0'>AI 评测平台</Title>
        </div>
        <Menu
          mode='inline'
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={handleMenuClick}
          style={{ 
            borderRight: 'none',
            color: '#fff'
          }}
          theme='dark'
        />
      </Sider>
      <Layout>
        <Header 
          style={{ 
            background: '#fff', 
            padding: '0 24px', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'space-between',
            boxShadow: '0 2px 8px rgba(0,0,0,0.06)'
          }}
        >
          <div className='flex items-center'>
            <span className='text-lg font-semibold text-gray-800'>{menuItems.find(item => item.key === location.pathname)?.label || '仪表盘'}</span>
          </div>
          <div className='flex items-center gap-4'>
            <Dropdown overlay={userMenu} trigger={['click']}>
              <Button 
                type='text' 
                icon={<Avatar size={32} icon={<User className='w-5 h-5' />} />}
                onClick={(e) => e.preventDefault()}
              >
                <ChevronDown className='w-4 h-4 ml-1' />
              </Button>
            </Dropdown>
          </div>
        </Header>
        <Content 
          style={{ 
            padding: '24px',
            background: '#f5f7fa'
          }}
        >
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};

export default AppLayout;
