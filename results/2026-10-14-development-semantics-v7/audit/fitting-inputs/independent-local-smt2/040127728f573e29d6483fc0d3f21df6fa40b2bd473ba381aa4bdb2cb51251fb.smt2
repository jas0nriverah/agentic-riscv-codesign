(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x76 (bvadd independent_opaque_0 (_ bv2576 32))))
(let ((?x334 (bvadd (bvadd independent_opaque_0 (_ bv2047 32)) (_ bv529 32))))
(and (distinct ?x334 ?x76) true))))
(check-sat)
