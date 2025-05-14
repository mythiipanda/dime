import { createClient } from '@supabase/supabase-js';
import { NextResponse } from 'next/server';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!supabaseUrl || !supabaseAnonKey) {
  console.error('[API Waitlist Route - Critical] Supabase URL or Anon Key is missing from environment variables. API will not function.');
  // In a production environment, you might want to throw an error or have more robust startup checks.
}

// Initialize Supabase client at the module level for reuse
const supabase = supabaseUrl && supabaseAnonKey ? createClient(supabaseUrl, supabaseAnonKey) : null;

if (!supabase) {
  // This log helps during deployment/startup if env vars are an issue.
  console.error('[API Waitlist Route - Critical] Supabase client failed to initialize. Check environment variables and server logs.');
}

export async function POST(request: Request) {
  if (!supabase) {
    // This check handles cases where the client might not have initialized due to missing env vars.
    return NextResponse.json({ error: 'Supabase client not available. Server configuration error.' }, { status: 500 });
  }

  try {
    const { email } = await request.json();

    if (!email || typeof email !== 'string' || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return NextResponse.json({ error: 'Invalid email address provided.' }, { status: 400 });
    }

    const { data, error: insertError } = await supabase
      .from('waitlist') 
      .insert([{ email: email }])
      .select(); 

    if (insertError) {
      console.error('[API Waitlist Route] Supabase insert error:', {
        message: insertError.message,
        details: insertError.details,
        code: insertError.code,
      });
      if (insertError.code === '23505') { // Unique constraint violation
        return NextResponse.json({ message: 'Email already on the waitlist.', email }, { status: 200 }); // Or 409 if preferred
      }
      return NextResponse.json({ error: 'Failed to add email to waitlist. Please try again later.' }, { status: 500 });
    }

    return NextResponse.json({ message: 'Successfully added to waitlist', data }, { status: 201 });

  } catch (err) {
    console.error('[API Waitlist Route] Unexpected error in POST handler:', err);
    const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred.';
    return NextResponse.json({ error: 'An unexpected error occurred. Please try again later.', details: errorMessage }, { status: 500 });
  }
} 