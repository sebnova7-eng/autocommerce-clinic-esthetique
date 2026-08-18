import React, { useEffect, useState } from 'react';

import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { api } from '@/lib/api';

export interface PatientOption {
  id: number;
  nom: string;
  prenom: string;
  telephone: string;
}

interface PatientAutocompleteProps {
  selectedPatient: PatientOption | null;
  onSelect: (patient: PatientOption | null) => void;
  label?: string;
  placeholder?: string;
}

export function PatientAutocomplete({
  selectedPatient,
  onSelect,
  label = 'Patient *',
  placeholder = 'Nom, prénom ou téléphone...',
}: PatientAutocompleteProps) {
  const [query, setQuery] = useState('');
  const [options, setOptions] = useState<PatientOption[]>([]);

  useEffect(() => {
    if (query.length < 2) {
      setOptions([]);
      return;
    }

    const timeout = setTimeout(async () => {
      try {
        const res = await api.get('/patients', { params: { search: query } });
        setOptions(Array.isArray(res.data) ? res.data.slice(0, 8) : []);
      } catch {
        setOptions([]);
      }
    }, 300);

    return () => clearTimeout(timeout);
  }, [query]);

  return (
    <div>
      <Label>{label}</Label>
      <Input
        value={selectedPatient ? `${selectedPatient.prenom} ${selectedPatient.nom}` : query}
        onChange={(e) => {
          setQuery(e.target.value);
          onSelect(null);
        }}
        placeholder={placeholder}
      />
      {options.length > 0 && !selectedPatient && (
        <div className="border rounded-md mt-1 max-h-32 overflow-y-auto">
          {options.map((patient) => (
            <button
              type="button"
              key={patient.id}
              className="w-full text-left px-3 py-2 hover:bg-muted text-sm"
              onClick={() => {
                onSelect(patient);
                setQuery('');
                setOptions([]);
              }}
            >
              {patient.prenom} {patient.nom} — {patient.telephone}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
