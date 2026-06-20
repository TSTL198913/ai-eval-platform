import { Layout } from 'antd';
import { Sidebar } from './Sidebar';
import { Header } from './Header';

const { Content } = Layout;

interface AppLayoutProps {
  children: React.ReactNode;
  title: string;
  currentPath: string;
}

export const AppLayout = ({ children, title, currentPath }: AppLayoutProps) => {
  return (
    <Layout className="h-screen">
      <Sidebar currentPath={currentPath} />
      <Layout className="flex flex-col">
        <Header title={title} />
        <Content className="flex-1 overflow-auto bg-gray-50 p-6">
          {children}
        </Content>
      </Layout>
    </Layout>
  );
};
