import React from 'react';

export const Modal: React.FC<{
  isOpen: boolean; onClose: () => void; title: string; subtitle?: string; children: React.ReactNode;
}> = ({ isOpen, onClose, title, subtitle, children }) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/40 backdrop-blur-sm p-0 sm:p-4"
         onClick={onClose}>
      <div className="bg-bg border border-line w-full sm:max-w-md rounded-t-2xl sm:rounded-xl max-h-[90vh] overflow-y-auto"
           onClick={(e) => e.stopPropagation()}>
        <div className="px-5 pt-5 pb-4 border-b border-line">
          <h2 className="text-[15px] font-semibold text-fg-strong">{title}</h2>
          {subtitle && <p className="text-2xs text-muted mt-0.5">{subtitle}</p>}
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
};

export const Field: React.FC<{ label: string; hint?: string; children: React.ReactNode }> = ({
  label, hint, children,
}) => (
  <label className="block">
    <span className="text-2xs text-muted">{label}</span>
    {children}
    {hint && <span className="block text-2xs text-faint mt-0.5">{hint}</span>}
  </label>
);

export const input =
  'mt-1 w-full bg-surface border border-line rounded-lg px-3 py-2 text-[13px] text-fg ' +
  'focus:outline-none focus:border-accent transition tnum';

export const button =
  'px-3.5 py-2 rounded-lg text-[13px] font-medium transition disabled:opacity-40';
