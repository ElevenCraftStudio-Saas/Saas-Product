'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { FirebaseError } from 'firebase/app';
import { useAuth } from '@/lib/auth-context';
import { Button } from '@/components/ui/button';
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { toast } from 'sonner';
import api from '@/lib/api';

const formSchema = z.object({
  email: z.string().email({ message: 'Please enter a valid email address.' }),
  password: z.string().min(6, { message: 'Password must be at least 6 characters.' }),
});

export default function LoginPage() {
  const router = useRouter();
  const { signInEmail, signUpEmail, signInGoogle } = useAuth();
  const [isLoading, setIsLoading] = useState(false);
  const [mode, setMode] = useState<'login' | 'signup'>('login');

  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: { email: '', password: '' },
  });

  function handleError(error: unknown) {
    const msg =
      error instanceof FirebaseError ? error.message : 'Authentication failed.';
    console.error('Auth error:', error);
    toast.error(msg);
  }

  async function routeByRole() {
    try {
      const me = (await api.get('/auth/me')).data as { role: string };
      router.push(me.role === 'admin' ? '/admin' : '/dashboard');
    } catch {
      router.push('/dashboard');
    }
  }

  async function onSubmit(values: z.infer<typeof formSchema>) {
    try {
      setIsLoading(true);
      if (mode === 'signup') {
        await signUpEmail(values.email, values.password);
        toast.success('Account created!');
      } else {
        await signInEmail(values.email, values.password);
        toast.success('Login successful!');
      }
      await routeByRole();
    } catch (error) {
      handleError(error);
    } finally {
      setIsLoading(false);
    }
  }

  async function onGoogle() {
    try {
      setIsLoading(true);
      await signInGoogle();
      toast.success('Login successful!');
      await routeByRole();
    } catch (error) {
      handleError(error);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-slate-50">
      <Card className="w-full max-w-md">
        <CardHeader className="space-y-1 text-center">
          <CardTitle className="text-3xl font-bold">WedFind AI</CardTitle>
          <CardDescription>
            {mode === 'login' ? 'Sign in to the photographer dashboard' : 'Create a studio account'}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Form {...form}>
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
              <FormField
                control={form.control}
                name="email"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Email</FormLabel>
                    <FormControl>
                      <Input placeholder="studio@example.com" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <FormField
                control={form.control}
                name="password"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Password</FormLabel>
                    <FormControl>
                      <Input type="password" placeholder="••••••••" {...field} />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
              <Button type="submit" className="w-full" disabled={isLoading}>
                {isLoading ? 'Please wait…' : mode === 'login' ? 'Login' : 'Sign up'}
              </Button>
            </form>
          </Form>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t" />
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-card px-2 text-slate-400">or</span>
            </div>
          </div>

          <Button variant="outline" className="w-full" onClick={onGoogle} disabled={isLoading}>
            Continue with Google
          </Button>
        </CardContent>
        <CardFooter className="flex justify-center border-t pt-6">
          <button
            type="button"
            className="text-sm text-slate-500 hover:text-slate-900"
            onClick={() => setMode(mode === 'login' ? 'signup' : 'login')}
          >
            {mode === 'login' ? "No account? Sign up" : 'Have an account? Login'}
          </button>
        </CardFooter>
      </Card>
    </div>
  );
}
