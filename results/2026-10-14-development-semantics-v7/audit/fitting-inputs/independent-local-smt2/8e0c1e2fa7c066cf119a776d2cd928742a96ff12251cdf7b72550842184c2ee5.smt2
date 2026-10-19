(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x15 (bvadd (bvshl independent_opaque_0 (bvand (_ bv16 32) (_ bv31 32))) (_ bv4294901760 32))))
(let ((?x809 (bvand (_ bv16 32) (_ bv31 32))))
(let ((?x85 (bvshl (bvadd independent_opaque_0 (_ bv4294967295 32)) ?x809)))
(and (distinct ?x85 ?x15) true)))))
(check-sat)
