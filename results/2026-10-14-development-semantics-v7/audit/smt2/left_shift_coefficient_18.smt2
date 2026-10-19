(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x207 (bvmul x (_ bv262144 32))))
(let ((?x205 (bvshl x (_ bv18 32))))
(and (distinct ?x205 ?x207) true))))
(check-sat)
