(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x101 (bvmul x (_ bv64 32))))
(let ((?x99 (bvshl x (_ bv6 32))))
(and (distinct ?x99 ?x101) true))))
(check-sat)
