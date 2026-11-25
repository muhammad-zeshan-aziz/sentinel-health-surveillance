import React from 'react';
import { TrendingUp, TrendingDown, Minus, Info } from 'lucide-react';

export const KPICard = ({
  title,
  value,
  subtitle,
  change,
  changeType, // 'increase' | 'decrease' | 'neutral'
  goodDirection = 'down', // 'down' (cases) or 'up' (coverage/timeliness)
  icon: Icon,
  colorScheme = 'teal',
  onClick,
  badgeText
}) => {
  const getSchemeStyles = () => {
    switch (colorScheme) {
      case 'teal':
        return {
          iconBg: 'bg-teal-50 text-teal-600 border-teal-200',
          hoverBorder: 'hover:border-teal-300'
        };
      case 'amber':
        return {
          iconBg: 'bg-amber-50 text-amber-600 border-amber-200',
          hoverBorder: 'hover:border-amber-300'
        };
      case 'rose':
        return {
          iconBg: 'bg-rose-50 text-rose-600 border-rose-200',
          hoverBorder: 'hover:border-rose-300'
        };
      case 'indigo':
        return {
          iconBg: 'bg-indigo-50 text-indigo-600 border-indigo-200',
          hoverBorder: 'hover:border-indigo-300'
        };
      case 'emerald':
        return {
          iconBg: 'bg-emerald-50 text-emerald-600 border-emerald-200',
          hoverBorder: 'hover:border-emerald-300'
        };
      default:
        return {
          iconBg: 'bg-slate-100 text-slate-600 border-slate-200',
          hoverBorder: 'hover:border-slate-300'
        };
    }
  };

  const scheme = getSchemeStyles();

  return (
    <div
      onClick={onClick}
      className={`bg-white rounded-xl border border-slate-200/90 p-4 shadow-xs transition-all duration-200 ${
        onClick ? 'cursor-pointer hover:shadow-md ' + scheme.hoverBorder : ''
      }`}
    >
      <div className="flex items-start justify-between">
        <div>
          <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1">
            {title}
          </span>
          <div className="text-2xl font-bold text-slate-900 tracking-tight flex items-baseline gap-2">
            <span>{value}</span>
            {badgeText && (
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 border border-slate-200">
                {badgeText}
              </span>
            )}
          </div>
        </div>

        <div className={`w-10 h-10 rounded-xl flex items-center justify-center border ${scheme.iconBg}`}>
          {Icon && <Icon className="w-5 h-5" />}
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between text-xs pt-2 border-t border-slate-100">
        <span className="text-slate-500 font-medium truncate max-w-[170px]" title={subtitle}>
          {subtitle}
        </span>

        {change !== undefined && change !== null && (
          <div
            className={`flex items-center gap-0.5 font-semibold ${
              changeType === 'increase'
                ? (goodDirection === 'up' ? 'text-emerald-600' : 'text-rose-600')
                : changeType === 'decrease'
                ? (goodDirection === 'up' ? 'text-rose-600' : 'text-emerald-600')
                : 'text-slate-500'
            }`}
          >
            {changeType === 'increase' && <TrendingUp className="w-3.5 h-3.5" />}
            {changeType === 'decrease' && <TrendingDown className="w-3.5 h-3.5" />}
            {changeType === 'neutral' && <Minus className="w-3.5 h-3.5" />}
            <span>{change}</span>
          </div>
        )}
      </div>
    </div>
  );
};
