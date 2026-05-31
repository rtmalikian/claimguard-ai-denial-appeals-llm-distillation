import { useCallback, useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { patientsApi } from '../api/client';
import type { AuthUser, PatientPayload, PatientResponse } from '../api/client';

interface PatientsProps {
  currentUser: AuthUser | null;
}

interface PatientFormState {
  id?: number;
  mrn: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
}

interface SearchState {
  patient_id: string;
  mrn: string;
  first_name: string;
  last_name: string;
  date_of_birth: string;
}

const emptyPatientForm: PatientFormState = {
  mrn: '',
  first_name: '',
  last_name: '',
  date_of_birth: '',
};

const emptySearch: SearchState = {
  patient_id: '',
  mrn: '',
  first_name: '',
  last_name: '',
  date_of_birth: '',
};

const formatDate = (value?: string | null) => {
  if (!value) return 'N/A';
  return value;
};

const displayName = (patient: PatientResponse) => {
  const name = [patient.first_name, patient.last_name].filter(Boolean).join(' ').trim();
  return name || 'N/A';
};

const normalize = (value?: string | null) => (value || '').trim().toLowerCase();

const getErrorMessage = (err: unknown) => {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const response = (err as { response?: { data?: { detail?: string } } }).response;
    if (response?.data?.detail) return response.data.detail;
  }
  return 'Request failed';
};

export default function Patients({ currentUser }: PatientsProps) {
  const [patients, setPatients] = useState<PatientResponse[]>([]);
  const [formData, setFormData] = useState<PatientFormState>(emptyPatientForm);
  const [searchData, setSearchData] = useState<SearchState>(emptySearch);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [searching, setSearching] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const canWrite = currentUser?.role === 'admin' || currentUser?.role === 'billing_staff';
  const canDelete = currentUser?.role === 'admin';
  const isEditing = formData.id != null;

  const identifierCount = useMemo(() => {
    return [
      searchData.patient_id,
      searchData.mrn,
      searchData.first_name,
      searchData.last_name,
      searchData.date_of_birth,
    ].filter((value) => value.trim()).length;
  }, [searchData]);

  const hasSearchCriteria = identifierCount > 0;
  const canSearchSafely = identifierCount >= 3;

  const buildPayload = (): PatientPayload => ({
    mrn: formData.mrn.trim(),
    first_name: formData.first_name.trim() || null,
    last_name: formData.last_name.trim() || null,
    date_of_birth: formData.date_of_birth || null,
  });

  const matchesSearch = (patient: PatientResponse) => {
    const patientId = searchData.patient_id.trim();
    if (patientId && String(patient.id) !== patientId) return false;

    const mrn = searchData.mrn.trim();
    if (mrn && normalize(patient.mrn) !== normalize(mrn)) return false;

    const firstName = searchData.first_name.trim();
    if (firstName && !normalize(patient.first_name).includes(normalize(firstName))) return false;

    const lastName = searchData.last_name.trim();
    if (lastName && !normalize(patient.last_name).includes(normalize(lastName))) return false;

    const dob = searchData.date_of_birth.trim();
    if (dob && patient.date_of_birth !== dob) return false;

    return true;
  };

  const loadPatients = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await patientsApi.list({ skip: 0, limit: 100 });
      setPatients(res.data);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadPatients();
  }, [loadPatients]);

  const resetForm = () => {
    setFormData(emptyPatientForm);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canWrite || !formData.mrn.trim()) return;

    setSaving(true);
    setError(null);
    setNotice(null);

    try {
      const payload = buildPayload();
      if (isEditing && formData.id != null) {
        await patientsApi.update(formData.id, payload);
        setNotice(`Patient #${formData.id} updated`);
      } else {
        const res = await patientsApi.create(payload);
        setNotice(`Patient #${res.data.id} created`);
      }

      resetForm();
      await loadPatients();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleEdit = (patient: PatientResponse) => {
    setFormData({
      id: patient.id,
      mrn: patient.mrn,
      first_name: patient.first_name || '',
      last_name: patient.last_name || '',
      date_of_birth: patient.date_of_birth || '',
    });
    setNotice(null);
    setError(null);
  };

  const handleDelete = async (patient: PatientResponse) => {
    if (!canDelete || !window.confirm(`Delete patient #${patient.id}?`)) return;

    setDeletingId(patient.id);
    setError(null);
    setNotice(null);

    try {
      await patientsApi.delete(patient.id);
      setNotice(`Patient #${patient.id} deleted`);
      await loadPatients();
      if (formData.id === patient.id) resetForm();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setDeletingId(null);
    }
  };

  const handleSearch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!hasSearchCriteria) {
      await loadPatients();
      return;
    }

    if (!canSearchSafely) {
      setError('Safe patient search requires at least 3 identifiers.');
      return;
    }

    setSearching(true);
    setError(null);
    setNotice(null);

    try {
      const patientId = searchData.patient_id.trim();
      const mrn = searchData.mrn.trim();

      if (patientId) {
        const res = await patientsApi.get(Number(patientId));
        setPatients(matchesSearch(res.data) ? [res.data] : []);
        return;
      }

      if (mrn) {
        const res = await patientsApi.getByMrn(mrn);
        setPatients(matchesSearch(res.data) ? [res.data] : []);
        return;
      }

      const res = await patientsApi.list({
        skip: 0,
        limit: 100,
        first_name: searchData.first_name.trim() || undefined,
        last_name: searchData.last_name.trim() || undefined,
        dob: searchData.date_of_birth || undefined,
      });
      setPatients(res.data.filter(matchesSearch));
    } catch (err) {
      const message = getErrorMessage(err);
      if (message.toLowerCase().includes('not found')) {
        setPatients([]);
      } else {
        setError(message);
      }
    } finally {
      setSearching(false);
    }
  };

  const handleResetSearch = async () => {
    setSearchData(emptySearch);
    setNotice(null);
    setError(null);
    await loadPatients();
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Patients</h1>
        </div>
        <div className="rounded-md bg-white px-3 py-2 text-sm text-gray-600 shadow">
          {currentUser?.role.replace('_', ' ') || 'viewer'}
        </div>
      </div>

      {(error || notice) && (
        <div className={`mb-6 rounded-md border p-4 text-sm ${error ? 'border-red-200 bg-red-50 text-red-700' : 'border-green-200 bg-green-50 text-green-700'}`}>
          {error || notice}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <section className="bg-white p-6 shadow">
          <h2 className="mb-4 text-xl font-semibold text-gray-900">{isEditing ? 'Edit Patient' : 'Create Patient'}</h2>
          {!canWrite && (
            <div className="mb-4 rounded-md bg-gray-50 p-3 text-sm text-gray-600">
              Your role has read-only access.
            </div>
          )}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700">MRN</label>
              <input
                type="text"
                value={formData.mrn}
                onChange={(event) => setFormData({ ...formData, mrn: event.target.value })}
                disabled={!canWrite}
                required
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-primary-500 focus:ring-primary-500 disabled:bg-gray-100"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">First Name</label>
              <input
                type="text"
                value={formData.first_name}
                onChange={(event) => setFormData({ ...formData, first_name: event.target.value })}
                disabled={!canWrite}
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-primary-500 focus:ring-primary-500 disabled:bg-gray-100"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Last Name</label>
              <input
                type="text"
                value={formData.last_name}
                onChange={(event) => setFormData({ ...formData, last_name: event.target.value })}
                disabled={!canWrite}
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-primary-500 focus:ring-primary-500 disabled:bg-gray-100"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Date of Birth</label>
              <input
                type="date"
                value={formData.date_of_birth}
                onChange={(event) => setFormData({ ...formData, date_of_birth: event.target.value })}
                disabled={!canWrite}
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-primary-500 focus:ring-primary-500 disabled:bg-gray-100"
              />
            </div>
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={!canWrite || saving || !formData.mrn.trim()}
                className="flex-1 rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {saving ? 'Saving...' : isEditing ? 'Save Changes' : 'Create Patient'}
              </button>
              {isEditing && (
                <button
                  type="button"
                  onClick={resetForm}
                  disabled={saving}
                  className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                >
                  Cancel
                </button>
              )}
            </div>
          </form>
        </section>

        <section className="bg-white p-6 shadow lg:col-span-2">
          <h2 className="mb-4 text-xl font-semibold text-gray-900">Patient Search</h2>
          <form onSubmit={handleSearch} className="grid grid-cols-1 gap-4 md:grid-cols-6">
            <div>
              <label className="block text-sm font-medium text-gray-700">Patient ID</label>
              <input
                type="number"
                min="1"
                value={searchData.patient_id}
                onChange={(event) => setSearchData({ ...searchData, patient_id: event.target.value })}
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-primary-500 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">MRN</label>
              <input
                type="text"
                value={searchData.mrn}
                onChange={(event) => setSearchData({ ...searchData, mrn: event.target.value })}
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-primary-500 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">First Name</label>
              <input
                type="text"
                value={searchData.first_name}
                onChange={(event) => setSearchData({ ...searchData, first_name: event.target.value })}
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-primary-500 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Last Name</label>
              <input
                type="text"
                value={searchData.last_name}
                onChange={(event) => setSearchData({ ...searchData, last_name: event.target.value })}
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-primary-500 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">DOB</label>
              <input
                type="date"
                value={searchData.date_of_birth}
                onChange={(event) => setSearchData({ ...searchData, date_of_birth: event.target.value })}
                className="mt-1 block w-full rounded-md border border-gray-300 p-2 shadow-sm focus:border-primary-500 focus:ring-primary-500"
              />
            </div>
            <div className="flex items-end gap-2">
              <button
                type="submit"
                disabled={searching || (hasSearchCriteria && !canSearchSafely)}
                className="flex-1 rounded-md bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {searching ? 'Searching...' : 'Search'}
              </button>
              <button
                type="button"
                onClick={handleResetSearch}
                disabled={searching}
                className="rounded-md border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                Reset
              </button>
            </div>
          </form>
          {hasSearchCriteria && !canSearchSafely && (
            <div className="mt-3 rounded-md bg-yellow-50 p-3 text-sm text-yellow-800">
              Add {3 - identifierCount} more identifier{3 - identifierCount === 1 ? '' : 's'} to search.
            </div>
          )}
        </section>
      </div>

      <section className="mt-6 overflow-hidden bg-white shadow">
        <div className="border-b border-gray-200 px-6 py-4">
          <h2 className="text-xl font-semibold text-gray-900">Patient Records</h2>
        </div>
        {loading ? (
          <div className="p-8 text-center text-gray-500">Loading...</div>
        ) : patients.length === 0 ? (
          <div className="p-8 text-center text-gray-500">No patients found</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500">ID</th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500">MRN</th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500">Name</th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500">DOB</th>
                  <th className="px-6 py-3 text-left text-xs font-medium uppercase text-gray-500">Created</th>
                  <th className="px-6 py-3 text-right text-xs font-medium uppercase text-gray-500">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {patients.map((patient) => (
                  <tr key={patient.id} className="hover:bg-gray-50">
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">#{patient.id}</td>
                    <td className="whitespace-nowrap px-6 py-4 font-mono text-sm text-gray-900">{patient.mrn}</td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-900">{displayName(patient)}</td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-600">{formatDate(patient.date_of_birth)}</td>
                    <td className="whitespace-nowrap px-6 py-4 text-sm text-gray-600">
                      {new Date(patient.created_at).toLocaleDateString()}
                    </td>
                    <td className="whitespace-nowrap px-6 py-4 text-right text-sm">
                      <button
                        type="button"
                        onClick={() => handleEdit(patient)}
                        disabled={!canWrite}
                        className="mr-3 font-medium text-primary-600 hover:text-primary-800 disabled:cursor-not-allowed disabled:text-gray-400"
                      >
                        Edit
                      </button>
                      {canDelete && (
                        <button
                          type="button"
                          onClick={() => handleDelete(patient)}
                          disabled={deletingId === patient.id}
                          className="font-medium text-red-600 hover:text-red-800 disabled:cursor-not-allowed disabled:text-gray-400"
                        >
                          {deletingId === patient.id ? 'Deleting...' : 'Delete'}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
