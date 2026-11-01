"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAuthStore } from "@/store/auth";
import { api, ApiError } from "@/lib/api";

const schema = z.object({
  title: z.string().min(3, "At least 3 characters").max(500),
  product_category: z.string().optional(),
  description: z.string().optional(),
});
type FormData = z.infer<typeof schema>;

export default function NewListingPage() {
  const router = useRouter();
  const { accessToken } = useAuthStore();
  const [serverError, setServerError] = useState("");

  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const onSubmit = async (data: FormData) => {
    setServerError("");
    try {
      const created = await api.listings.create(accessToken!, {
        title: data.title,
        product_category: data.product_category || undefined,
        description: data.description || undefined,
      });
      router.push(`/dashboard/listings/${created.id}/dialogue`);
    } catch (e) {
      setServerError(e instanceof ApiError ? e.message : "Failed to create listing");
    }
  };

  return (
    <div className="max-w-lg">
      <h1 className="text-2xl font-bold text-ink mb-1">Create IP Listing</h1>
      <p className="text-sm text-muted mb-6">Give your IP a name to start the AI documentation session.</p>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-ink-soft mb-1">IP / Product Name</label>
          <input
            {...register("title")}
            className="w-full px-3 py-2 border border-line-strong rounded-lg text-sm focus:ring-2 focus:ring-accent"
            placeholder="e.g. BioClear Wound Gel v2"
          />
          {errors.title && <p className="text-red-500 text-xs mt-1">{errors.title.message}</p>}
        </div>

        <div>
          <label className="block text-sm font-medium text-ink-soft mb-1">Product Category <span className="text-muted">(optional)</span></label>
          <input
            {...register("product_category")}
            className="w-full px-3 py-2 border border-line-strong rounded-lg text-sm focus:ring-2 focus:ring-accent"
            placeholder="e.g. Medical Devices, Food & Beverage, Chemicals"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-ink-soft mb-1">Brief Description <span className="text-muted">(optional)</span></label>
          <textarea
            {...register("description")}
            rows={3}
            className="w-full px-3 py-2 border border-line-strong rounded-lg text-sm focus:ring-2 focus:ring-accent resize-none"
            placeholder="A short description for your own reference"
          />
        </div>

        {serverError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm">{serverError}</div>
        )}

        <button
          type="submit"
          disabled={isSubmitting}
          className="w-full bg-accent text-white py-2.5 rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-50 transition-colors"
        >
          {isSubmitting ? "Creating listing…" : "Start AI Documentation"}
        </button>
      </form>
    </div>
  );
}
