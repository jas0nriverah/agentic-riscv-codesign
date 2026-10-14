(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x76 (bvadd independent_opaque_0 (bvadd independent_opaque_1 (_ bv4294967293 32)))))
(let ((?x37 (bvadd (bvadd independent_opaque_0 independent_opaque_1) (_ bv4294967293 32))))
(and (distinct ?x37 ?x76) true))))
(check-sat)
