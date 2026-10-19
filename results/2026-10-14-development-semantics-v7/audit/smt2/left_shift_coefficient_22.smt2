(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x243 (bvmul x (_ bv4194304 32))))
(let ((?x241 (bvshl x (_ bv22 32))))
(and (distinct ?x241 ?x243) true))))
(check-sat)
