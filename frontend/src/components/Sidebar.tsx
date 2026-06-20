import {
  Layout,
  Menu,
  Button,
  Tooltip,
} from 'antd';
import {
  LayoutDashboard,
  Cpu,
  Database,
  FileText,
  DollarSign,
  Activity,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from 'lucide-react';
import { useAuthStore, useAppStore } from '@/stores/authStore';

const { Sider } = Layout;

const menuItems = [
  { key: '/', icon: LayoutDashboard, label: '仪表盘' },
  { key: '/evaluators', icon: Cpu, label: '评估器管理' },
  { key: '/models', icon: Database, label: '模型对比' },
  { key: '/records', icon: FileText, label: '评估记录' },
  { key: '/cost', icon: DollarSign, label: '成本监控' },
  { key: '/health', icon: Activity, label: '系统健康' },
];

interface SidebarProps {
  currentPath: string;
}

export const Sidebar = ({ currentPath }: SidebarProps) => {
  const { sidebarCollapsed, toggleSidebar } = useAppStore();
  const { logout, user } = useAuthStore();

  return (
    <Sider
      theme="dark"
      width={sidebarCollapsed ? 64 : 200}
      className="bg-[#1e3a5f] border-r border-white/10 transition-all duration-300"
    >
      <div className="h-full flex flex-col">
        <div className="p-4 flex items-center justify-between border-b border-white/10">
          <div className="flex items-center gap-2 overflow-hidden">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[#667eea] to-[#764ba2] flex items-center justify-center flex-shrink-0">
              <Sparkles className="w-5 h-5 text-white" />
            </div>
            {!sidebarCollapsed && (
              <span className="text-white font-bold text-lg whitespace-nowrap">
                AI评测平台
              </span>
            )}
          </div>
          <Button
            type="text"
            icon={sidebarCollapsed ? <ChevronRight /> : <ChevronLeft />}
            onClick={toggleSidebar}
            className="text-white/70 hover:text-white hover:bg-white/10"
          />
        </div>

        <Menu
          mode="inline"
          theme="dark"
          selectedKeys={[currentPath]}
          items={menuItems.map((item) => ({
            key: item.key,
            icon: <item.icon className="w-5 h-5" />,
            label: item.label,
          }))}
          className="flex-1 bg-transparent"
          style={{ border: 'none' }}
        />

        <div className="p-4 border-t border-white/10">
          <div className="flex items-center gap-2 mb-4">
            <div className="w-8 h-8 rounded-full bg-white/20 flex items-center justify-center">
              <span className="text-white text-sm font-medium">
                {user?.username?.charAt(0) || 'U'}
              </span>
            </div>
            {!sidebarCollapsed && (
              <div className="overflow-hidden">
                <div className="text-white text-sm font-medium truncate">
                  {user?.username || 'User'}
                </div>
                <div className="text-white/50 text-xs truncate">
                  {user?.role || 'user'}
                </div>
              </div>
            )}
          </div>
          <Tooltip title={sidebarCollapsed ? '退出登录' : undefined}>
            <Button
              type="text"
              icon={<LogOut className="w-5 h-5" />}
              onClick={logout}
              className="w-full justify-start text-white/70 hover:text-white hover:bg-white/10"
            >
              {!sidebarCollapsed && '退出登录'}
            </Button>
          </Tooltip>
        </div>
      </div>
    </Sider>
  );
};
