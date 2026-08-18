import React, { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useBranding } from '@/contexts/BrandingContext';
import { useLocation } from 'wouter';
import LanguageSwitcher from '@/components/LanguageSwitcher';
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarFooter,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarTrigger,
  SidebarProvider,
} from '@/components/ui/sidebar';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Calendar,
  Users,
  FileText,
  Pill,
  DollarSign,
  Heart,
  Briefcase,
  MessageSquare,
  Settings,
  LogOut,
  ChevronDown,
  Menu,
  Zap,
  Activity,
  Headphones,
  BarChart,
  Mail,
} from 'lucide-react';

interface NavItem {
  label: string;
  href: string;
  icon: React.ReactNode;
  roles?: string[];
  children?: NavItem[];
}

const NAV_ITEMS: NavItem[] = [
  {
    label: 'Tableau de bord',
    href: '/dashboard',
    icon: <Menu className="w-4 h-4" />,
  },
  {
    label: 'Dashboard IA',
    href: '/dashboard-ia',
    icon: <Zap className="w-4 h-4" />,
  },
  {
    label: 'Automatisations IA',
    href: '/workflows',
    icon: <Activity className="w-4 h-4" />,
    roles: ['directrice', 'admin'],
  },
  {
    label: 'Copilote CRM',
    href: '/copilote-crm',
    icon: <Headphones className="w-4 h-4" />,
    roles: ['directrice', 'medecin', 'estheticienne', 'admin'],
  },
  {
    label: 'Business Intelligence',
    href: '/analytics',
    icon: <BarChart className="w-4 h-4" />,
    roles: ['directrice', 'admin'],
  },
  {
    label: 'Agenda',
    href: '/agenda',
    icon: <Calendar className="w-4 h-4" />,
  },
  {
    label: 'Patients',
    href: '/patients',
    icon: <Users className="w-4 h-4" />,
  },
  {
    label: 'Dossier médical',
    href: '/patients',
    icon: <FileText className="w-4 h-4" />,
    roles: ['directrice', 'medecin', 'estheticienne', 'admin'],
  },
  {
    label: 'Gestion Stocks',
    href: '/stock',
    icon: <Pill className="w-4 h-4" />,
  },
  {
    label: 'Délégués & Labos',
    href: '/delegues',
    icon: <Users className="w-4 h-4" />,
    roles: ['directrice', 'medecin', 'admin'],
  },
  {
    label: 'Factures & Dépenses',
    href: '/invoices',
    icon: <DollarSign className="w-4 h-4" />,
  },
  {
    label: 'Commissions',
    href: '/commissions',
    icon: <DollarSign className="w-4 h-4" />,
    roles: ['directrice', 'admin', 'commercial'],
  },
  {
    label: 'Fidélité & Parrainage',
    href: '/loyalty',
    icon: <Heart className="w-4 h-4" />,
  },
  {
    label: 'Recrutement',
    href: '/recruitment',
    icon: <Briefcase className="w-4 h-4" />,
    roles: ['directrice', 'assistante', 'admin'],
  },
  {
    label: 'Social CRM',
    href: '/social',
    icon: <MessageSquare className="w-4 h-4" />,
  },
  {
    label: 'Messagerie Équipe',
    href: '/equipe',
    icon: <Mail className="w-4 h-4" />,
  },
  {
    label: 'Tarification',
    href: '/settings/actes',
    icon: <DollarSign className="w-4 h-4" />,
    roles: ['directrice', 'admin'],
  },
  {
    label: 'Paramètres',
    href: '/settings',
    icon: <Settings className="w-4 h-4" />,
    roles: ['directrice', 'admin'],
  },
];

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export const DashboardLayout: React.FC<DashboardLayoutProps> = ({ children }) => {
  const { user, logout } = useAuth();
  const { branding } = useBranding();
  const [location, setLocation] = useLocation();
  const [open, setOpen] = useState(false);

  // Filter nav items based on user role
  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.roles || (user && item.roles.includes(user.role))
  );

  const isActive = (href: string) => location === href;

  return (
    <SidebarProvider>
    <div className="flex h-screen bg-background">
      <Sidebar>
        <SidebarHeader className="border-b px-4 py-4">
          <div className="flex items-center gap-3">
            {branding?.logo_url && (
              <img
                src={branding.logo_url}
                alt="Logo"
                className="h-8 w-8 object-contain"
              />
            )}
            <div className="flex-1 min-w-0">
              <h1 className="text-sm font-bold truncate">
                {branding?.nom_clinique || 'Clinique'}
              </h1>
              <p className="text-xs text-muted-foreground truncate">
                {user?.prenom} {user?.nom}
              </p>
            </div>
          </div>
        </SidebarHeader>

        <SidebarContent>
          <SidebarMenu>
            {visibleItems.map((item) => (
              <SidebarMenuItem key={item.href}>
                <SidebarMenuButton
                  asChild
                  isActive={isActive(item.href)}
                  onClick={() => setLocation(item.href)}
                >
                  <div className="flex items-center gap-2 cursor-pointer">
                    {item.icon}
                    <span>{item.label}</span>
                  </div>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarContent>

        <SidebarFooter className="border-t p-4">
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" className="w-full justify-between">
                <span className="text-xs text-muted-foreground truncate">
                  {user?.email}
                </span>
                <ChevronDown className="w-4 h-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuItem onClick={logout}>
                <LogOut className="w-4 h-4 mr-2" />
                Déconnexion
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </SidebarFooter>
      </Sidebar>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="border-b bg-card px-6 py-4 flex items-center justify-between">
          <SidebarTrigger />
          <div className="flex items-center gap-4">
            <LanguageSwitcher />
            <div className="text-sm text-muted-foreground">
              Rôle: <span className="font-semibold text-foreground">{user?.role}</span>
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-auto">
          <div className="p-6">
            {children}
          </div>
        </main>
      </div>
    </div>
    </SidebarProvider>
  );
};
